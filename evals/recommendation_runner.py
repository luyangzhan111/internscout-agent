"""Run the frozen Stage19 comparison without a model, network or database writes."""

import argparse
from collections import Counter
import json
from pathlib import Path
from urllib.parse import urlsplit

import app

from app.agent.tools.job_query import JobQueryPort
from app.matching.contracts import CandidateProfile
from app.matching.matcher import CandidateMatcher
from app.matching.skill_extractor import JobSkillExtractor
from app.recommendations.quality import quality_rank_key
from app.recommendations.service import RecommendationService
from app.schemas.job_response import JobRead
from evals.recommendation_dataset import ALGORITHM_FILES, DIMENSIONS, ROOT, STATES, Dataset, _verify_files, digest, load_dataset
from evals.recommendation_scorers import (
    aggregate_direction_safety, aggregate_metrics, ratio, score_direction_safety, score_ranking,
)


class SnapshotQuery(JobQueryPort):
    """A detached, read-only query port over the same frozen source records."""

    def __init__(self, jobs: list[JobRead]):
        self.jobs = [job.model_copy(deep=True) for job in jobs]

    def search_jobs(self, *, city=None, company=None, skill=None, page=1, page_size=10):
        if any(value is not None for value in (city, company, skill)):
            raise ValueError("The comparison must not prefilter the frozen corpus")
        start = (page - 1) * page_size
        return [j.model_copy(deep=True) for j in self.jobs[start:start + page_size]], len(self.jobs)

    def get_job_by_id(self, job_id):
        return next((j.model_copy(deep=True) for j in self.jobs if j.id == job_id), None)


def _confusion(labels):
    matrix = {actual: {predicted: 0 for predicted in STATES} for actual in STATES}
    for actual, predicted in labels:
        matrix[actual][predicted] += 1
    correct = sum(matrix[state][state] for state in STATES)
    total = sum(sum(row.values()) for row in matrix.values())
    return {"correct": correct, "total": total, "accuracy": ratio(correct, total),
            "matrix_rows_gold_columns_predicted": matrix}


def run_dataset(dataset: Dataset, *, k: int = 5) -> dict:
    if type(k) is not int or not 1 <= k <= 50:
        raise ValueError("k must be an integer between 1 and 50")
    if dataset.fingerprints.get("algorithm_files"):
        application_root = Path(app.__file__).resolve().parent.parent
        _verify_files(application_root, dataset.fingerprints["algorithm_files"], ALGORITHM_FILES,
                      algorithm_line_endings=True)
    source_jobs = [record.job for record in dataset.records]
    id_keys = {job.id: key for key, job in dataset.primary.items()}
    matcher, extractor = CandidateMatcher(), JobSkillExtractor()
    service = RecommendationService(SnapshotQuery(source_jobs))
    results = []
    direction_safety_profiles = {}
    all_condition_labels = {dimension: [] for dimension in DIMENSIONS}
    all_overall_labels = []
    ranking_versions, rules_versions = set(), set()
    for profile in dataset.profiles:
        gold = {key: dataset.gold[(profile.profile_id, key)] for key in dataset.primary}
        baseline = [matcher.match(candidate=CandidateProfile(skills=profile.candidate.skills), job=job,
                                  evidence=extractor.extract(job))
                    for job in dataset.primary.values() if job.status != "closed"]
        baseline.sort(key=lambda card: (-card.match_score, -len(card.matched_skills), card.job.id))
        baseline_order = [id_keys[card.job.id] for card in baseline]
        batch = service.recommend(profile.candidate, limit=k)
        ranking_versions.add(batch.ranking_version)
        cards, diagnostics = [], {}
        partition = Counter()
        condition_labels = {dimension: [] for dimension in DIMENSIONS}
        overall_labels = []
        direction_pairs = []
        for key, job in dataset.primary.items():
            single = RecommendationService(SnapshotQuery([job])).recommend(profile.candidate, limit=1)
            if single.recommendations:
                card = single.recommendations[0]
                cards.append(card)
                decision, disposition = card.eligibility, "retained"
            elif single.direction_excluded:
                card = single.direction_excluded[0]
                decision, disposition = card.eligibility, "direction_mismatch"
            else:
                card = None
                decision = single.excluded[0]
                disposition = "closed" if job.status == "closed" else "not_met"
            label = disposition if disposition != "retained" else decision.overall
            rules_versions.add(decision.rules_version)
            partition[label] += 1
            predicted_conditions = {check.dimension: check.status for check in decision.checks}
            for dimension in DIMENSIONS:
                pair = (gold[key].eligibility[dimension], predicted_conditions[dimension])
                condition_labels[dimension].append(pair)
                all_condition_labels[dimension].append(pair)
            pair = (gold[key].overall, decision.overall)
            overall_labels.append(pair)
            all_overall_labels.append(pair)
            fit = card.direction_fit.model_dump(mode="json") if card is not None else None
            if fit is not None:
                direction_pairs.append((gold[key].direction, fit["status"]))
            diagnostics[key] = {
                "disposition": disposition, "predicted_overall": decision.overall,
                "predicted_conditions": predicted_conditions,
                "reason": decision.reason, "blocking_reasons": decision.blocking_reasons,
                "checks": [c.model_dump(mode="json") for c in decision.checks],
                "direction_fit": fit,
                "direction_not_assessed_reason": "qualification_or_closed_short_circuit" if fit is None else None,
            }
            support = getattr(card, "ranking_support", None) if card is not None else None
            if support is not None:
                diagnostics[key]["ranking_support"] = support.model_dump(mode="json")
        cards.sort(key=quality_rank_key)
        current_order = [id_keys[card.job.id] for card in cards]
        expected_top = [id_keys[card.job.id] for card in batch.recommendations]
        if current_order[:k] != expected_top:
            raise ValueError("Per-job diagnostics disagree with the production batch ranking")
        for name in ("met", "unknown", "not_met", "closed", "direction_mismatch"):
            if partition[name] != getattr(batch.counts, name):
                raise ValueError("Per-job diagnostics disagree with production partition counts")
        if batch.counts.evaluated != len(dataset.primary):
            raise ValueError("Production and baseline evaluated different independent job pools")
        def describe(key):
            job, judgement = dataset.primary[key], gold[key]
            return {"job_key": key, "job_id": job.id, "title": job.title, "company": job.company,
                    "city": job.city, "source_url": job.source_url,
                    "gold_relevance": judgement.relevance, "gold_overall": judgement.overall,
                    "gold_direction": judgement.direction, "gold_reason": judgement.reason,
                    "gold_evidence": [q.model_dump(mode="json", exclude_none=True) for q in judgement.evidence]}
        baseline_scores = {id_keys[c.job.id]: c for c in baseline}
        current_scores = {id_keys[c.job.id]: c for c in cards}
        systems = {}
        for name, ordered, score_cards in (("baseline", baseline_order, baseline_scores),
                                           ("current", current_order, current_scores)):
            metrics = score_ranking(ordered, set(ordered), gold, k=k)
            ranked = []
            for position, key in enumerate(ordered, 1):
                card = score_cards[key]
                ranked.append({"position": position, **describe(key), "skill_score": card.match_score,
                               "matched_skills": list(card.matched_skills),
                               "detected_skills": list(card.detected_job_skills)})
            systems[name] = {"metrics": metrics, "top_k": ordered[:k], "ranking": ranked,
                             "excluded": [describe(key) for key in dataset.primary if key not in ordered]}
        wrong_baseline = [key for key in baseline_order[:k]
                          if gold[key].overall == "not_met" or gold[key].direction == "unrelated"]
        missed = systems["current"]["metrics"]["missed_useful_keys"]
        direction_correct = sum(actual == predicted for actual, predicted in direction_pairs)
        direction_safety_profiles[profile.profile_id] = score_direction_safety(diagnostics, gold)
        results.append({
            "profile_id": profile.profile_id, "label": profile.label,
            "candidate": profile.candidate.model_dump(mode="json"), "systems": systems,
            "production_counts": batch.counts.model_dump(mode="json"),
            "production_data_scope": batch.data_scope.model_dump(mode="json"),
            "current_diagnostics": diagnostics,
            "eligibility_agreement": {"overall": _confusion(overall_labels),
                                      "dimensions": {dim: _confusion(pairs) for dim, pairs in condition_labels.items()}},
            "direction_agreement": {"assessed": len(direction_pairs), "pool": len(gold),
                                    "correct": direction_correct,
                                    "accuracy_assessed_only": ratio(direction_correct, len(direction_pairs)),
                                    "skipped_due_to_qualification_or_closed": len(gold) - len(direction_pairs)},
            "examples": {
                "baseline_clearly_wrong_removed_from_current_top_k": [describe(key) for key in wrong_baseline if key not in current_order[:k]],
                "current_false_excluded_useful": [{**describe(key), "production": diagnostics[key]} for key in missed],
                "current_top_k_not_relevant": [describe(key) for key in current_order[:k] if gold[key].relevance < 2],
            },
        })
    summaries = {name: aggregate_metrics([r["systems"][name]["metrics"] for r in results])
                 for name in ("baseline", "current")}
    return {
        "schema_version": 1, "comparison": "skill-only-vs-selected-production-recommender", "k": k,
        "ranking_versions": sorted(ranking_versions), "eligibility_rules_versions": sorted(rules_versions),
        "protocol": {
            "baseline": "Same isolated/grouped snapshot, excludes closed; skill coverage, matched count, ID; no target/eligibility filter.",
            "current": "Unmodified production RecommendationService; per-primary replay recovers full retained/excluded sets and verifies batch counts/top-K.",
            "relevant_threshold": 2, "gain": "2^relevance-1", "precision_denominator": "K, including unfilled slots",
            "ndcg_without_any_gain": "N/A (JSON null), excluded from macro denominator",
            "false_exclusion": "Relevant (>=2), nonblocked, direction not unrelated; absent from complete retained set, not merely below K. Unknown retained as potentially useful.",
            "three_state_agreement": "Only current produces eligibility decisions; baseline N/A. Direction agreement is assessed-only because production short-circuits known qualification failures.",
            "direction_safety": "Hard direction exclusions are counted separately for gold aligned/uncertain. Qualification/closed short circuits are skipped. Retained uncertainty is partitioned by gold direction and relevance; use full candidate recall and ranking precision alongside hard-exclusion safety.",
            "claims": "Comparison of complete filtering and ranking systems; not an LLM benefit, independent human study or causal attribution to one rule.",
        },
        "fingerprints": {**dataset.fingerprints, "evaluation_implementation": {
            name: digest(ROOT / name) for name in (
                "evals/recommendation_dataset.py", "evals/recommendation_runner.py", "evals/recommendation_scorers.py",
            )
        }},
        "corpus": {"source_records": len(dataset.records), "independent_jobs": len(dataset.primary),
                   "companies": dict(Counter(j.company for j in dataset.primary.values())),
                   "source_hosts": sorted({urlsplit(j.source_url).hostname for j in dataset.primary.values()}),
                   "profiles": len(dataset.profiles), "judged_pairs": len(dataset.gold)},
        "summary": summaries,
        "direction_safety": aggregate_direction_safety(list(direction_safety_profiles.values())),
        "direction_safety_profiles": direction_safety_profiles,
        "eligibility_agreement": {"overall": _confusion(all_overall_labels),
                                  "dimensions": {dim: _confusion(pairs) for dim, pairs in all_condition_labels.items()}},
        "profiles": results,
    }


def _number(value):
    return "N/A" if value is None else f"{value:.3f}"


def render_markdown(report: dict) -> str:
    def safe(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    k = report["k"]
    lines = ["# 冻结岗位推荐对照（单版本）", "",
             f"同一冻结快照：{report['corpus']['independent_jobs']} 个独立岗位，"
             f"{report['corpus']['profiles']} 组合成条件，{report['corpus']['judged_pairs']} 对标签。", "",
             "标签为 AI 辅助阅读原文及项目内复核，不是独立真人标注。岗位状态与采集快照绑定，不证明当前仍在招聘。", "",
             f"P@{k} 固定除以 {k}；少返回的空位计零。相关性 ≥2 表示值得进一步核对，待确认不等于不符合。",
             f"本意图 P@{k} 理论上限为 min({k}, 金标相关岗位数)/{k}，仅解释岗位供给限制，不替代固定分母指标。",
             "nDCG 无任何非零金标增益时为 N/A，不计入该项均值；单列其意图数量。误排除看完整保留集合，排在展示上限外不算被过滤。", "",
             "比较的是整套过滤和排序的效果，不将差异归因于 LLM 或某一单项规则。两组均隔离样例、跨来源分组并排除已关闭岗位。", "",
             f"| 方案 | P@{k} | nDCG@{k} | 有效 nDCG 意图数 | 返回/空位分母 | 明确错误/返回 | 值得核对岗位误排除/候选对 |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for name, label in (("baseline", "简单技能"), ("current", "当前推荐")):
        m = report["summary"][name]
        lines.append(f"| {label} | {_number(m['precision_at_k_macro'])} | {_number(m['ndcg_at_k_macro'])} | "
                     f"{m['ndcg_intent_denominator']} | {m['returned']}/{m['display_slots']} | "
                     f"{m['clearly_wrong_in_top_k']}/{m['returned']} | {m['false_excluded_useful_pairs']}/{m['useful_pool_pairs']} |")
    lines.extend(["", "## 每组条件的岗位供给", "",
                  f"| 条件 | 金标相关岗位数 | P@{k} 理论上限 |", "| --- | --- | --- |"])
    for item in report["profiles"]:
        m = item["systems"]["current"]["metrics"]
        lines.append(f"| {safe(item['label'])} | {m['relevant_pool_count']} | {_number(m['maximum_precision_at_k'])} |")
    lines.append("")
    lines.append(f"P@{k} 理论上限宏平均：{_number(report['summary']['current']['maximum_precision_at_k_macro'])}。")
    lines.extend(["", "## 每组条件", "",
                  f"| 条件 | 方案 | 相关/固定{k}位 | nDCG | 明确方向不符 | 明确资格不符 | 值得核对岗位误排除 |", "| --- | --- | --- | --- | --- | --- | --- |"])
    for item in report["profiles"]:
        for name, label in (("baseline", "技能"), ("current", "当前")):
            m = item["systems"][name]["metrics"]
            lines.append(f"| {safe(item['label'])} | {label} | {m['relevant_in_top_k']}/{k} | {_number(m['ndcg_at_k'])} | "
                         f"{m['wrong_direction_in_top_k']} | {m['wrong_conditions_in_top_k']} | {m['false_excluded_useful_count']}/{m['useful_pool_count']} |")
    agreement = report["eligibility_agreement"]
    lines.extend(["", "## 三态判断一致性", "", "仅当前推荐有资格判断，技能基线为 N/A。分母包含待确认，不将其删除。", "",
                  "| 范围 | 一致/标签数 | 一致率 |", "| --- | --- | --- |"])
    for name, m in [("整体资格", agreement["overall"]), *agreement["dimensions"].items()]:
        lines.append(f"| {name} | {m['correct']}/{m['total']} | {_number(m['accuracy'])} |")
    safety = report.get("direction_safety")
    if safety is not None:
        lines.extend(["", "## 方向硬排和待确认保留", "",
                      "资格/关闭短路不计为方向判断正确。硬排安全、无关过滤、待确认噪声及完整候选召回应一起阅读。", "",
                      "| 项目 | 分子/分母 |", "| --- | --- |",
                      f"| 方向已评估 | {safety['assessed_count']}/{safety['targeted_pool_count']} |",
                      f"| 金标方向一致被误硬排 | {safety['false_hard_excluded_aligned_count']} |",
                      f"| 金标方向待确认被误硬排 | {safety['false_hard_excluded_uncertain_count']} |",
                      f"| 误硬排/已评估金标非无关 | {safety['false_hard_excluded_count']}/{safety['gold_aligned_or_uncertain_assessed_count']} |",
                      f"| 金标无关被硬排 | {safety['correctly_hard_excluded_unrelated_count']}/{safety['gold_unrelated_assessed_count']} |",
                      f"| 保留待确认中的弱/无关岗位 | {safety['retained_uncertain_weak_or_irrelevant_count']}/{safety['retained_uncertain_count']} |",
                      f"| 保留待确认中的金标无关岗位 | {safety['retained_uncertain_gold_unrelated_count']}/{safety['retained_uncertain_count']} |"])
    for item in report["profiles"]:
        lines.extend(["", f"## {safe(item['label'])}", ""])
        for name, label in (("baseline", "简单技能"), ("current", "当前推荐")):
            lines.extend([f"### {label}前 {k} 名", "", "| 排名 | 岗位 | 公司 | 金标相关性 | 金标资格 |", "| --- | --- | --- | --- | --- |"])
            for row in item["systems"][name]["ranking"][:k]:
                lines.append(f"| {row['position']} | [{safe(row['title'])}]({row['source_url']}) | {safe(row['company'])} | {row['gold_relevance']} | {row['gold_overall']} |")
            if not item["systems"][name]["ranking"]:
                lines.append("| — | 无返回 | — | — | — |")
        lines.extend(["", "### 保留的失败与变化案例", ""])
        for category, label in (("baseline_clearly_wrong_removed_from_current_top_k", "技能基线的明确错误退出当前前五"),
                                ("current_false_excluded_useful", "当前误排除的值得核对岗位"),
                                ("current_top_k_not_relevant", "当前前五中的弱相关/无关岗位")):
            examples = item["examples"][category]
            lines.append(f"- {label}：{len(examples)} 条。")
            for example in examples:
                text = f"  - [{safe(example['title'])}]({example['source_url']})（{safe(example['company'])}）：{safe(example['gold_reason'])}"
                if "production" in example:
                    decision = example["production"]
                    if decision["disposition"] == "direction_mismatch":
                        reason = decision["direction_fit"]["reason"]
                        text += f"；系统按方向排除：{safe(reason)}（资格仍为 {safe(decision['predicted_overall'])}）"
                    else:
                        text += f"；系统排除原因：{safe(decision['reason'])}"
                lines.append(text)
    lines.extend(["", "## 可复现性与边界", "", "- 完整排名、每项判断/原文依据、混淆矩阵、全部误排除及 SHA-256 指纹见同名 JSON。",
                  "- 方向判断可能在资格阻断后短路；JSON 单列已判断数量与跳过数量，不宣称全量方向准确率。",
                  "- 本轮是小样本、目的性采样的离线对照，不外推到全部招聘市场、真实用户满意度或录用率。",
                  "- 用本批结果调规则后，该批转为开发回归；新的效果验证应另收留出数据。", ""])
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True, dest="json_path")
    parser.add_argument("--markdown", type=Path, required=True)
    parser.add_argument("--algorithm-root", type=Path)
    parser.add_argument("--algorithm-manifest", default="algorithm_freeze.json")
    args = parser.parse_args(argv)
    directory = args.dataset.resolve()
    outputs = [args.json_path.resolve(), args.markdown.resolve()]
    if outputs[0] == outputs[1] or any(path.is_relative_to(directory) for path in outputs):
        parser.error("Reports must have distinct paths outside the frozen dataset directory")
    try:
        active_root = Path(app.__file__).resolve().parent.parent
        if args.algorithm_root is not None and args.algorithm_root.resolve() != active_root:
            raise ValueError("The selected algorithm root is not the imported application; use an isolated version run.")
        report = run_dataset(load_dataset(directory, algorithm_root=args.algorithm_root,
                                          algorithm_manifest=args.algorithm_manifest))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Evaluation input rejected: {exc}\n")
    for path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
    outputs[0].write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    outputs[1].write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"independent_jobs": report["corpus"]["independent_jobs"],
                      "profiles": report["corpus"]["profiles"], "summary": report["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
