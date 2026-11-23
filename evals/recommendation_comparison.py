"""Replay an archived application and compare it with the current rules offline."""

import argparse
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
BASELINES = {name: ROOT / "evals/baselines" / name for name in ("stage19", "stage20", "stage21", "stage22")}
BASELINE = BASELINES["stage19"]  # Preserve the original CLI/API default.
DEGREE_ONLY_BASELINE = ROOT / "evals/baselines/stage22_degree_only"
LOCATION_PHASE_BASELINE = ROOT / "evals/baselines/stage23_degree_only"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


@contextmanager
def baseline_application(baseline: Path = BASELINE):
    """Verify every member before extracting a local, immutable code baseline."""
    baseline = Path(baseline).resolve()
    manifest = json.loads((baseline / "manifest.json").read_text(encoding="utf-8"))
    archive = baseline / "application.zip"
    if digest(archive) != manifest["archive_sha256"]:
        raise ValueError("The archived application SHA-256 differs.")
    files = {**manifest["files"], "algorithm_freeze.json": manifest["source_manifest_sha256"]}
    runtime = ROOT / "tmp"
    runtime.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="stage20-baseline-", dir=runtime) as temporary:
        destination = Path(temporary).resolve()
        if not destination.is_relative_to(runtime.resolve()):
            raise ValueError("Baseline extraction must stay inside the explicit runtime directory.")
        with ZipFile(archive) as source:
            if len(source.namelist()) != len(files) or set(source.namelist()) != set(files):
                raise ValueError("The archive contains missing, duplicate or unexpected members.")
            for info in source.infolist():
                relative = PurePosixPath(info.filename)
                target = (destination / info.filename).resolve()
                if (relative.is_absolute() or ".." in relative.parts or "\\" in info.filename
                        or ":" in info.filename or not target.is_relative_to(destination)
                        or info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000):
                    raise ValueError("Unsafe archive member path or symbolic link.")
                content = source.read(info)
                if sha256(content).hexdigest() != files[info.filename]:
                    raise ValueError(f"Archived source bytes differ: {info.filename}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
        yield destination


_BOOTSTRAP = r'''
import runpy, socket, sys
from pathlib import Path
application_root, project_root = sys.argv[1:3]
sys.path[:] = [application_root, project_root] + [p for p in sys.path if p not in ('', application_root, project_root)]
def offline(*args, **kwargs):
    raise RuntimeError('Version comparisons are offline; network access is disabled')
socket.create_connection = offline
socket.socket.connect = offline
socket.socket.connect_ex = offline
sys.argv = ['evals.recommendation_runner'] + sys.argv[3:]
runpy.run_module('evals.recommendation_runner', run_name='__main__')
'''


def run_version(directory: Path, application_root: Path, *, algorithm_manifest="algorithm_freeze.json") -> dict:
    """Import only the selected application version in a fresh, offline process."""
    directory, application_root = Path(directory).resolve(), Path(application_root).resolve()
    runtime = ROOT / "tmp"
    runtime.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="stage20-evaluation-", dir=runtime) as temporary:
        temporary = Path(temporary).resolve()
        if not temporary.is_relative_to(runtime.resolve()):
            raise ValueError("Evaluation runtime must stay inside its explicit temporary directory.")
        output = temporary / "result.json"
        environment = os.environ.copy()
        for name in ("DEEPSEEK_API_KEY", "INTERNSCOUT_EMBEDDING_API_KEY", "INTERNSCOUT_EMBEDDING_BASE_URL"):
            environment.pop(name, None)
        environment["PYTHONIOENCODING"] = "utf-8"
        command = [sys.executable, "-X", "utf8", "-c", _BOOTSTRAP,
                   str(application_root), str(ROOT), "--dataset", str(directory),
                   "--algorithm-root", str(application_root), "--algorithm-manifest", algorithm_manifest,
                   "--json", str(output), "--markdown", str(temporary / "result.md")]
        result = subprocess.run(command, cwd=temporary, env=environment, capture_output=True,
                                text=True, encoding="utf-8", timeout=120)
        if result.returncode:
            raise ValueError(f"Isolated version evaluation failed: {result.stderr[-3000:]}")
        return json.loads(output.read_text(encoding="utf-8"))


def _safety(report: dict) -> dict:
    overall = report["eligibility_agreement"]["overall"]["matrix_rows_gold_columns_predicted"]
    degree = report["eligibility_agreement"]["dimensions"]["degree"]["matrix_rows_gold_columns_predicted"]
    def count(matrix, state):
        return sum(matrix[state].values())
    blocked, degree_blocked = count(overall, "not_met"), count(degree, "not_met")
    compatible = count(overall, "met") + count(overall, "unknown")
    false_blocks = overall["met"]["not_met"] + overall["unknown"]["not_met"]
    return {"known_qualification_blocks_recalled": overall["not_met"]["not_met"],
            "known_qualification_blocks": blocked,
            "known_qualification_block_recall": overall["not_met"]["not_met"] / blocked if blocked else None,
            "degree_state_blocks_recalled": degree["not_met"]["not_met"],
            "degree_state_blocks": degree_blocked,
            "degree_state_block_recall": degree["not_met"]["not_met"] / degree_blocked if degree_blocked else None,
            "false_qualification_blocks": false_blocks, "gold_nonblocked_pairs": compatible,
            "false_qualification_block_rate": false_blocks / compatible if compatible else None}


def _location_phase_checks(middle_report: dict, fixed: dict) -> list[dict]:
    """A location ablation can change qualification partitions, not other rules."""
    dimensions = {"graduation_year", "degree", "experience", "city", "internship_duration"}
    labels = {"graduation_year": "毕业届次", "degree": "学历", "experience": "工作经验",
              "city": "城市", "internship_duration": "可实习时长"}
    if middle_report.get("k") != fixed.get("k") or middle_report.get("ranking_versions") != fixed.get("ranking_versions"):
        raise ValueError("Location ablation changed the display limit or ranking version.")
    checks = []
    for middle, new in zip(middle_report["profiles"], fixed["profiles"], strict=True):
        if any(middle.get(name) != new.get(name) for name in (
                "profile_id", "label", "candidate", "production_data_scope")) or (
                middle["systems"]["baseline"] != new["systems"]["baseline"]):
            raise ValueError("Location ablation changed profiles, source scope or shared skill baseline.")
        old_diagnostics, new_diagnostics = middle["current_diagnostics"], new["current_diagnostics"]
        if set(old_diagnostics) != set(new_diagnostics):
            raise ValueError("Location ablation must assess the same complete candidate set.")
        changed, released, blocked, jointly_assessed = [], [], [], []
        for key, old in old_diagnostics.items():
            current = new_diagnostics[key]
            pair_checks = []
            for decision in (old, current):
                items = decision["checks"]
                by_dimension = {item["dimension"]: item for item in items}
                if len(items) != 5 or set(by_dimension) != dimensions or set(decision["predicted_conditions"]) != dimensions:
                    raise ValueError("Location ablation requires all five unique condition checks.")
                if any(item["status"] != decision["predicted_conditions"][dimension] for dimension, item in by_dimension.items()):
                    raise ValueError("Location ablation condition statuses disagree with complete checks.")
                statuses = set(decision["predicted_conditions"].values())
                if not statuses <= {"met", "not_met", "unknown"}:
                    raise ValueError("Location ablation contains an invalid condition status.")
                closed = decision["disposition"] == "closed"
                expected = "not_met" if closed or "not_met" in statuses else "unknown" if "unknown" in statuses else "met"
                if decision["predicted_overall"] != expected:
                    raise ValueError("Location ablation overall qualification is not attributable to its checks.")
                blockers = [f"{labels[item['dimension']]}：{item['reason']}" for item in items if item["status"] == "not_met"]
                if closed:
                    blockers.insert(0, "岗位已标记关闭，当前不可作为可投岗位。")
                if decision["blocking_reasons"] != blockers:
                    raise ValueError("Location ablation blocking reasons disagree with its hard condition checks.")
                fit = decision["direction_fit"]
                expected_disposition = ("closed" if closed else "not_met" if expected == "not_met" else
                                        "direction_mismatch" if fit is not None and fit["status"] == "unrelated" else "retained")
                if decision["disposition"] != expected_disposition or ((fit is None) != (expected_disposition in {"closed", "not_met"})):
                    raise ValueError("Location ablation changed retention or direction assessment without a qualification cause.")
                if decision["direction_not_assessed_reason"] != ("qualification_or_closed_short_circuit" if fit is None else None):
                    raise ValueError("Location ablation direction short-circuit reason disagrees with qualification.")
                pair_checks.append(by_dimension)
            old_checks, new_checks = pair_checks
            if any(old_checks[dimension] != new_checks[dimension] for dimension in dimensions - {"city"}):
                raise ValueError("Location ablation changed a complete noncity condition check.")
            if {d: s for d, s in old["predicted_conditions"].items() if d != "city"} != {
                    d: s for d, s in current["predicted_conditions"].items() if d != "city"}:
                raise ValueError("Location ablation changed noncity predicted conditions.")
            if (old["disposition"] == "closed") != (current["disposition"] == "closed"):
                raise ValueError("Location ablation changed a job's closed status.")
            if old_checks["city"] != new_checks["city"]:
                changed.append(key)
            elif any(old[name] != current[name] for name in ("predicted_overall", "reason", "blocking_reasons")):
                raise ValueError("Location ablation changed qualification without changing the city check.")
            if old["predicted_overall"] == "not_met" and current["predicted_overall"] != "not_met":
                if (old_checks["city"]["status"] != "not_met" or new_checks["city"]["status"] == "not_met"
                        or any(new_checks[d]["status"] == "not_met" for d in dimensions - {"city"})):
                    raise ValueError("A released location block still has a noncity hard block or lacks a city cause.")
                released.append(key)
            if old["predicted_overall"] != "not_met" and current["predicted_overall"] == "not_met":
                if new_checks["city"]["status"] != "not_met" or old_checks["city"]["status"] == "not_met":
                    raise ValueError("A new location qualification block lacks a city cause.")
                blocked.append(key)
            if old["direction_fit"] is not None and current["direction_fit"] is not None:
                jointly_assessed.append(key)
                if (old["direction_fit"] != current["direction_fit"] or old.get("ranking_support") != current.get("ranking_support")
                        or ("ranking_support" in old) != ("ranking_support" in current)):
                    raise ValueError("Location ablation changed jointly assessed direction or ranking support.")
            varying = {"checks", "predicted_conditions", "predicted_overall", "reason", "blocking_reasons",
                       "disposition", "direction_fit", "direction_not_assessed_reason", "ranking_support"}
            if {n: v for n, v in old.items() if n not in varying} != {n: v for n, v in current.items() if n not in varying}:
                raise ValueError("Location ablation changed an unrelated diagnostic.")
        rankings = []
        for row in (middle, new):
            ranking = row["systems"]["current"]["ranking"]
            by_key = {item["job_key"]: item for item in ranking}
            diagnostics = row["current_diagnostics"]
            retained = {key for key, decision in diagnostics.items() if decision["disposition"] == "retained"}
            if len(by_key) != len(ranking) or set(by_key) != retained:
                raise ValueError("Location ablation ranking must cover the complete retained set exactly.")
            counts = {name: 0 for name in ("met", "unknown", "not_met", "closed", "direction_mismatch")}
            for decision in diagnostics.values():
                counts[decision["predicted_overall"] if decision["disposition"] == "retained" else decision["disposition"]] += 1
            counts.update(evaluated=len(diagnostics), returned=min(row["systems"]["current"]["metrics"]["k"], len(retained)))
            if row["production_counts"] != counts:
                raise ValueError("Location ablation production counts disagree with qualification partitions.")
            rankings.append(by_key)
        before, after = rankings
        for key in set(before) & set(after):
            if any(before[key][name] != after[key][name] for name in ("skill_score", "matched_skills", "detected_skills")):
                raise ValueError("Location ablation changed shared retained skill evidence or scores.")
        if not (set(after) - set(before)) <= set(released) or not (set(before) - set(after)) <= set(blocked):
            raise ValueError("Location ablation changed the retained partition without a city qualification cause.")
        checks.append({"profile_id": new["profile_id"], "assessed_count": len(old_diagnostics),
                       "changed_city_count": len(changed), "changed_city_keys": sorted(changed),
                       "released_qualification_count": len(released), "released_qualification_keys": sorted(released),
                       "new_qualification_block_count": len(blocked), "new_qualification_block_keys": sorted(blocked),
                       "joint_direction_assessed_count": len(jointly_assessed),
                       "shared_retained_count": len(set(before) & set(after)),
                       "newly_retained_keys": sorted(set(after) - set(before)),
                       "removed_retained_keys": sorted(set(before) - set(after)),
                       "production_counts_before": middle["production_counts"], "production_counts_after": new["production_counts"],
                       "same_noncity_checks": True, "same_joint_direction_and_ranking_support": True,
                       "same_shared_retained_skills": True})
    return checks


def compare(directory: Path, *, previous: dict, fixed: dict, baseline: Path = BASELINE,
            degree_only: dict | None = None, location_phase_baseline: bool = False) -> dict:
    """Combine already isolated runs without changing or filtering any labels."""
    if location_phase_baseline and degree_only is None:
        raise ValueError("Location ablation requires the archived degree-only intermediate run.")
    if previous["corpus"] != fixed["corpus"]:
        raise ValueError("The two versions evaluated different corpora.")
    if previous["fingerprints"]["data_files"] != fixed["fingerprints"]["data_files"]:
        raise ValueError("The two versions used different frozen data or labels.")
    profiles = []
    for old, new in zip(previous["profiles"], fixed["profiles"], strict=True):
        if (old["profile_id"] != new["profile_id"] or old["candidate"] != new["candidate"]
                or old["systems"]["baseline"] != new["systems"]["baseline"]):
            raise ValueError("The profile inputs or shared skill baseline changed across versions.")
        old_missed = set(old["systems"]["current"]["metrics"]["missed_useful_keys"])
        new_missed = set(new["systems"]["current"]["metrics"]["missed_useful_keys"])
        profiles.append({"profile_id": old["profile_id"], "label": old["label"],
                         "recovered_useful": sorted(old_missed - new_missed),
                         "newly_missed_useful": sorted(new_missed - old_missed)})
    baseline = Path(baseline).resolve()
    report = {"schema_version": 1, "scope": Path(directory).name,
            "protocol": f"Same frozen pool and labels; skill baseline, isolated archived {baseline.name}, isolated fixed production rules. No network or model calls.",
            "corpus": fixed["corpus"], "changes": profiles,
            "summary": {"skill_baseline": previous["summary"]["baseline"],
                        "previous_recommender": previous["summary"]["current"],
                        "fixed_recommender": fixed["summary"]["current"]},
            "qualification_safety": {"previous": _safety(previous), "fixed": _safety(fixed)},
            "direction_safety": {"previous": previous["direction_safety"], "fixed": fixed["direction_safety"]},
            "versions": {"previous": previous, "fixed": fixed},
            "baseline_version": baseline.name,
            "archived_application_sha256": digest(baseline / "application.zip"),
            "archive_manifest_sha256": digest(baseline / "manifest.json"),
            "comparison_implementation_sha256": digest(Path(__file__))}
    if degree_only is not None:
        if (degree_only["corpus"] != fixed["corpus"]
                or degree_only["fingerprints"]["data_files"] != fixed["fingerprints"]["data_files"]):
            raise ValueError("The degree-only ablation used different frozen inputs.")
        checks = _location_phase_checks(degree_only, fixed) if location_phase_baseline else []
        for middle, new in ([] if location_phase_baseline else zip(degree_only["profiles"], fixed["profiles"], strict=True)):
            if (middle["profile_id"] != new["profile_id"] or middle["candidate"] != new["candidate"]
                    or middle["systems"]["baseline"] != new["systems"]["baseline"]):
                raise ValueError("The degree-only ablation changed profiles or shared skill baseline.")
            if middle["production_counts"] != new["production_counts"]:
                raise ValueError("Ranking must not change the degree-only candidate partition.")
            if set(middle["current_diagnostics"]) != set(new["current_diagnostics"]):
                raise ValueError("Ranking must assess the same complete candidate set.")
            for key, decision in middle["current_diagnostics"].items():
                # The only permitted extra diagnostic is the new explanation of
                # ordering. Qualification, direction and retention remain exact.
                plain = {name: value for name, value in decision.items() if name != "ranking_support"}
                current = {name: value for name, value in new["current_diagnostics"][key].items() if name != "ranking_support"}
                if plain != current:
                    raise ValueError("Ranking changed degree-only qualification, direction or retention.")
            before = middle["systems"]["current"]["ranking"]
            after = new["systems"]["current"]["ranking"]
            if {item["job_key"] for item in before} != {item["job_key"] for item in after}:
                raise ValueError("Ranking cannot remove or add degree-only retained candidates.")
            checks.append({"profile_id": new["profile_id"], "retained_count": len(after),
                           "same_complete_candidate_set": True,
                           "same_qualification_and_direction": True})
        report["summary"]["degree_only_recommender"] = degree_only["summary"]["current"]
        report["qualification_safety"]["degree_only"] = _safety(degree_only)
        report["direction_safety"]["degree_only"] = degree_only["direction_safety"]
        report["versions"]["degree_only"] = degree_only
        intermediate_archive = LOCATION_PHASE_BASELINE if location_phase_baseline else DEGREE_ONLY_BASELINE
        report["degree_only_archive_sha256"] = digest(intermediate_archive / "application.zip")
        report["degree_only_archive_manifest_sha256"] = digest(intermediate_archive / "manifest.json")
        if location_phase_baseline:
            report["location_ablation_checks"] = checks
            report["protocol"] += (" Stage23 degree-only archived intermediate and full rules differ only in city checks; "
                                   "the other four complete checks, profiles and inputs are identical. Qualification partitions "
                                   "may change due to city; jointly assessed direction/ranking support and shared retained skills remain exact.")
        else:
            report["ranking_ablation_checks"] = checks
            report["protocol"] += " Degree-only archived ablation uses identical qualifications, directions and complete retained set."
    return report


def comparison_markdown(report: dict) -> str:
    def n(value):
        return "N/A" if value is None else f"{value:.3f}"
    def safe(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    corpus = report["corpus"]
    stage = {"stage19": "Stage 20", "stage20": "Stage 21", "stage21": "Stage 22", "stage22": "Stage 23"}.get(report.get("baseline_version"), "规则修复")
    has_middle = "degree_only" in report["versions"]
    count = "四" if has_middle else "三"
    lines = [f"# {stage}：规则修复{count}组对照", "", f"修复前基线：{safe(report.get('baseline_version', 'stage19'))}。数据范围：{safe(report['scope'])}。"
             f"{corpus['independent_jobs']}岗、{corpus['profiles']}档案、{corpus['judged_pairs']}对标签。", "",
             "标签为AI辅助原文标注、项目内复核；新旧版在隔离进程运行，同一数据/金标、同一技能基线，网络和真实模型关闭。", "",
             "P@5固定五个位置，相关性≥2为值得核对；漏筛基于完整保留集合。展示位置和正相关候选对是不同分母。", "",
             "| 方案 | 相关/展示位置 | P@5 | nDCG@5 | 实际返回/展示位置 | 明确错误/实际返回 | 相关候选对误排除 |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    names = [("skill_baseline", "简单技能"), ("previous_recommender", "修复前推荐")]
    versions = [("previous", "修复前")]
    if has_middle:
        names.append(("degree_only_recommender", "仅学历修复"))
        versions.append(("degree_only", "仅学历修复"))
    names.append(("fixed_recommender", "修复后推荐"))
    versions.append(("fixed", "修复后"))
    for key, label in names:
        m = report["summary"][key]
        lines.append(f"| {label} | {m['relevant_in_top_k']}/{m['display_slots']} | {n(m['precision_at_k_macro'])} | "
                     f"{n(m['ndcg_at_k_macro'])} | {m['returned']}/{m['display_slots']} | {m['clearly_wrong_in_top_k']}/{m['returned']} | "
                     f"{m['false_excluded_useful_pairs']}/{m['useful_pool_pairs']} |")
    lines.extend(["", "## 资格安全性", "", "| 版本 | 明确资格阻断召回 | 学历/在读阻断召回 | 对金标未阻断项的误阻断 |", "| --- | --- | --- | --- |"])
    for key, label in versions:
        m = report["qualification_safety"][key]
        lines.append(f"| {label} | {m['known_qualification_blocks_recalled']}/{m['known_qualification_blocks']} | "
                     f"{m['degree_state_blocks_recalled']}/{m['degree_state_blocks']} | "
                     f"{m['false_qualification_blocks']}/{m['gold_nonblocked_pairs']} |")
    lines.extend(["", "## 方向硬排与待确认保留", "",
                  "方向未评估（资格阻断或关闭短路）不算方向判对。金标一致/待确认被硬排与待确认保留的噪声同时报告，避免全判待确认看似安全。", "",
                  "| 版本 | 方向已评估/目标候选对 | 金标一致误硬排 | 金标待确认误硬排 | 误硬排/已评估金标非无关 | 金标无关硬排/已评估无关 | 保留待确认 | 其中弱/无关 | 其中金标明确无关 |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"])
    for key, label in versions:
        m = report["direction_safety"][key]
        lines.append(f"| {label} | {m['assessed_count']}/{m['targeted_pool_count']} | {m['false_hard_excluded_aligned_count']} | "
                     f"{m['false_hard_excluded_uncertain_count']} | {m['false_hard_excluded_count']}/{m['gold_aligned_or_uncertain_assessed_count']} | "
                     f"{m['correctly_hard_excluded_unrelated_count']}/{m['gold_unrelated_assessed_count']} | {m['retained_uncertain_count']} | "
                     f"{m['retained_uncertain_weak_or_irrelevant_count']}/{m['retained_uncertain_count']} | {m['retained_uncertain_gold_unrelated_count']} |")
    lines.extend(["", "完整候选召回以金标相关且未资格阻断者为分母；展示前五之外仍被保留的不算漏筛。", "",
                  "| 方案 | 相关候选保留/完整相关池 | 完整候选召回 | 明确错误/固定展示位置 |", "| --- | --- | --- | --- |"])
    for key, label in names:
        m = report["summary"][key]
        lines.append(f"| {label} | {m['useful_pool_pairs'] - m['false_excluded_useful_pairs']}/{m['useful_pool_pairs']} | "
                     f"{n(m['useful_retention_recall'])} | {m['clearly_wrong_in_top_k']}/{m['display_slots']} |")
    lines.extend(["", "## 每份档案（含退步）", "", "| 条件 | 方案 | 金标相关数 | P@5供给上限 | 相关/5 | nDCG@5 | 明确错误 | 相关候选对误排除 |", "| --- | --- | --- | --- | --- | --- | --- | --- |"])
    for old, new in zip(report["versions"]["previous"]["profiles"], report["versions"]["fixed"]["profiles"], strict=True):
        rows = [(old, "baseline", "技能"), (old, "current", "修复前")]
        if has_middle:
            middle = next(p for p in report["versions"]["degree_only"]["profiles"] if p["profile_id"] == new["profile_id"])
            rows.append((middle, "current", "仅学历修复"))
        rows.append((new, "current", "修复后"))
        for row, system, label in rows:
            m = row["systems"][system]["metrics"]
            lines.append(f"| {safe(row['label'])} | {label} | {m['relevant_pool_count']} | {n(m['maximum_precision_at_k'])} | "
                         f"{m['relevant_in_top_k']}/5 | {n(m['ndcg_at_k'])} | {m['clearly_wrong_in_top_k']} | "
                         f"{m['false_excluded_useful_count']}/{m['useful_pool_count']} |")
    for old, new in zip(report["versions"]["previous"]["profiles"], report["versions"]["fixed"]["profiles"], strict=True):
        lines.extend(["", f"## {safe(new['label'])}", ""])
        rows = [(old, "修复前")]
        if has_middle:
            rows.append((next(p for p in report["versions"]["degree_only"]["profiles"] if p["profile_id"] == new["profile_id"]), "仅学历修复"))
        rows.append((new, "修复后"))
        for row, label in rows:
            lines.extend([f"### {label}前五", "", "| 排名 | 岗位 | 公司 | 金标相关性 | 金标资格 |", "| --- | --- | --- | --- | --- |"])
            for item in row["systems"]["current"]["ranking"][:5]:
                lines.append(f"| {item['position']} | [{safe(item['title'])}]({item['source_url']}) | {safe(item['company'])} | {item['gold_relevance']} | {item['gold_overall']} |")
            if not row["systems"]["current"]["ranking"]:
                lines.append("| — | 无返回 | — | — | — |")
        change = next(item for item in report["changes"] if item["profile_id"] == new["profile_id"])
        lines.extend(["", f"- 恢复的相关候选：{safe('、'.join(change['recovered_useful']) or '无')}。",
                      f"- 新增漏筛：{safe('、'.join(change['newly_missed_useful']) or '无')}。"])
        for example in new["examples"]["current_false_excluded_useful"]:
            decision = example["production"]
            reason = (decision["direction_fit"]["reason"] if decision["disposition"] == "direction_mismatch" else decision["reason"])
            lines.append(f"- 留存错误：[{safe(example['title'])}]({example['source_url']})；金标：{safe(example['gold_reason'])}；系统：{safe(reason)}。")
    if "location_ablation_checks" in report:
        lines.extend(["", "## 地点阶段消融约束", "", "仅学历修复中间版与完整版只允许城市检查变化；其余四维完整检查、档案、原文及金标输入保持精确相同。",
                      "城市判断可以改变资格阻断、方向短路与完整保留集合；两版均进入方向评估的岗位，其方向判断及排序支持必须相同，共同保留岗位的技能分数和命中/识别技能必须相同。",
                      "逐档报告城市变化、解除资格阻断、新增资格阻断及保留集合变化；仅学历修复到完整版的差异归于城市处理，不能归因于排序改进。", "",
                      "| 档案 | 城市检查变化 | 解除资格阻断 | 新增资格阻断 | 新保留/移出保留 |", "| --- | --- | --- | --- | --- |"])
        for item in report["location_ablation_checks"]:
            lines.append(f"| {safe(item['profile_id'])} | {item['changed_city_count']}/{item['assessed_count']} | "
                         f"{item['released_qualification_count']} | {item['new_qualification_block_count']} | "
                         f"{len(item['newly_retained_keys'])}/{len(item['removed_retained_keys'])} |")
    elif has_middle:
        lines.extend(["", "## 排序消融约束", "", "仅学历修复与完整版逐岗资格、方向及完整保留集合完全相同，排序没有通过删除待确认岗位改善指标。",
                      "新排序收益应同时对照仅学历版及修复前，不能把学历恢复的候选归因于排序。"])
    lines.extend(["", "## 解释边界", "", "- 已用于开发的历史岗位仅作回归，修复后的旧集收益不能当新数据泛化证据。",
                  "- 新岗位目的性采样、公司/模板不均衡，标签未独立真人验证；岗位详情可读不证明仍可投。",
                  "- 无金标正例的类别用N/A与分子分母解释；保留总体、每档案退步、误阻断和漏筛，不预设提升。",
                  "- 完整新旧诊断、原文、五维混淆矩阵、归档与实现指纹见同名JSON。", ""])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True, dest="json_path")
    parser.add_argument("--markdown", type=Path, required=True)
    parser.add_argument("--baseline", choices=tuple(BASELINES), default="stage19", help="Archived application used for the before/replay run")
    phase = parser.add_mutually_exclusive_group()
    phase.add_argument("--degree-only-baseline", action="store_true", help="Include the frozen Stage22 degree-only ranking ablation using degree_only_algorithm_freeze.json")
    phase.add_argument("--location-phase-baseline", action="store_true", help="Include the frozen Stage23 degree-only intermediate; allow only city-check changes using degree_only_algorithm_freeze.json")
    parser.add_argument("--replay-archive", action="store_true", help="Replay the selected archived application using the dataset's original algorithm_freeze.json")
    args = parser.parse_args(argv)
    if args.replay_archive and (args.degree_only_baseline or args.location_phase_baseline):
        parser.error("A historical replay cannot also run the degree-only comparison.")
    directory = args.dataset.resolve()
    outputs = (args.json_path.resolve(), args.markdown.resolve())
    if outputs[0] == outputs[1] or any(path.is_relative_to(directory) for path in outputs):
        parser.error("Comparison outputs must be distinct paths outside the frozen input directory.")
    baseline = BASELINES[args.baseline]
    with baseline_application(baseline) as old_root:
        previous = run_version(directory, old_root, algorithm_manifest=(
            "algorithm_freeze.json" if args.replay_archive else "previous_algorithm_freeze.json"))
    if args.replay_archive:
        from evals.recommendation_runner import render_markdown
        for path in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
        outputs[0].write_text(json.dumps(previous, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
        outputs[1].write_text(render_markdown(previous), encoding="utf-8", newline="\n")
        print(json.dumps({"replayed_archived_application": True, "baseline_version": args.baseline,
                          "archive_sha256": digest(baseline / "application.zip"), "summary": previous["summary"]}, ensure_ascii=False))
        return
    fixed = run_version(directory, ROOT)
    middle = None
    if args.degree_only_baseline or args.location_phase_baseline:
        intermediate_archive = LOCATION_PHASE_BASELINE if args.location_phase_baseline else DEGREE_ONLY_BASELINE
        with baseline_application(intermediate_archive) as middle_root:
            middle = run_version(directory, middle_root, algorithm_manifest="degree_only_algorithm_freeze.json")
    report = compare(directory, previous=previous, fixed=fixed, baseline=baseline, degree_only=middle,
                     location_phase_baseline=args.location_phase_baseline)
    for path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
    outputs[0].write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    outputs[1].write_text(comparison_markdown(report), encoding="utf-8", newline="\n")
    print(json.dumps({"corpus": report["corpus"], "summary": report["summary"], "qualification_safety": report["qualification_safety"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
