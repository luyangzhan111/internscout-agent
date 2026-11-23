"""The location phase permits city-driven partition changes, not rule drift."""

import copy
from contextlib import contextmanager
import json

import pytest

import evals.recommendation_comparison as comparison
from evals.recommendation_runner import run_dataset
from tests.evaluation.test_recommendation_quality import tiny_dataset


@pytest.fixture
def phase_reports(monkeypatch):
    # These reports are synthetic contract fixtures, never published accuracy
    # results. The existing archive supplies only verifiable metadata.
    monkeypatch.setattr(comparison, "LOCATION_PHASE_BASELINE", comparison.BASELINES["stage21"])
    result = run_dataset(tiny_dataset())
    result["fingerprints"]["data_files"] = {"synthetic-fixture": "identical-inputs"}
    return copy.deepcopy(result), copy.deepcopy(result), copy.deepcopy(result)


def city_check(report, key="job-3"):
    return next(item for item in report["profiles"][0]["current_diagnostics"][key]["checks"] if item["dimension"] == "city")


def block_retained_by_city(report):
    row = report["profiles"][0]
    decision = row["current_diagnostics"]["job-3"]
    city = city_check(report)
    city.update(status="not_met", reason="合成城市硬限制不满足。", unknown_reason=None, next_step="")
    decision.update(predicted_overall="not_met", reason="至少一项明确投递条件不满足。",
                    blocking_reasons=["城市：合成城市硬限制不满足。"], disposition="not_met",
                    direction_fit=None, direction_not_assessed_reason="qualification_or_closed_short_circuit")
    decision["predicted_conditions"]["city"] = "not_met"
    decision.pop("ranking_support", None)
    row["production_counts"]["unknown"] -= 1
    row["production_counts"]["not_met"] += 1
    row["production_counts"]["returned"] = 0
    row["systems"]["current"]["ranking"] = []
    row["systems"]["current"]["top_k"] = []


def combine(tmp_path, reports):
    old, middle, fixed = reports
    return comparison.compare(tmp_path, previous=old, degree_only=middle, fixed=fixed,
                              baseline=comparison.BASELINES["stage22"], location_phase_baseline=True)


def test_location_phase_uses_separate_intermediate_archive_and_reports(phase_reports, tmp_path):
    report = combine(tmp_path, phase_reports)
    assert report["versions"]["degree_only"] == phase_reports[1]
    assert report["summary"]["degree_only_recommender"] == phase_reports[1]["summary"]["current"]
    assert report["degree_only_archive_sha256"] == comparison.digest(comparison.LOCATION_PHASE_BASELINE / "application.zip")
    assert "ranking_ablation_checks" not in report
    checks = report["location_ablation_checks"][0]
    assert checks["assessed_count"] == 3
    assert checks["changed_city_keys"] == []
    assert checks["same_noncity_checks"]
    assert "differ only in city checks" in report["protocol"]
    assert "identical qualifications" not in report["protocol"]
    text = comparison.comparison_markdown(report)
    assert "Stage 23" in text and "四组" in text and "地点阶段消融约束" in text
    assert "城市判断可以改变资格阻断" in text
    assert "完整保留集合完全相同" not in text


def test_city_release_can_add_a_candidate_and_begin_direction_assessment(phase_reports, tmp_path):
    block_retained_by_city(phase_reports[1])
    report = combine(tmp_path, phase_reports)
    checks = report["location_ablation_checks"][0]
    assert checks["changed_city_keys"] == ["job-3"]
    assert checks["released_qualification_keys"] == ["job-3"]
    assert checks["released_qualification_count"] == 1
    assert checks["newly_retained_keys"] == ["job-3"]
    assert checks["shared_retained_count"] == 0
    assert checks["production_counts_before"] != checks["production_counts_after"]


def test_new_city_block_can_remove_a_retained_candidate(phase_reports, tmp_path):
    block_retained_by_city(phase_reports[2])
    checks = combine(tmp_path, phase_reports)["location_ablation_checks"][0]
    assert checks["new_qualification_block_keys"] == ["job-3"]
    assert checks["new_qualification_block_count"] == 1
    assert checks["removed_retained_keys"] == ["job-3"]
    assert checks["released_qualification_keys"] == []


def test_city_explanation_change_does_not_require_partition_change(phase_reports, tmp_path):
    city_check(phase_reports[2])["notes"].append("地理符合，不代表出勤安排已核实。")
    checks = combine(tmp_path, phase_reports)["location_ablation_checks"][0]
    assert checks["changed_city_count"] == 1
    assert checks["changed_city_keys"] == ["job-3"]
    assert checks["released_qualification_count"] == 0
    assert checks["production_counts_before"] == checks["production_counts_after"]


@pytest.mark.parametrize("defect", [
    "corpus", "data", "profile", "label", "baseline", "source_scope", "limit", "ranking_version",
    "diagnostic_keys", "noncity_status", "noncity_reason", "noncity_evidence", "noncity_note",
    "predicted_noncity", "duplicate_check", "missing_check", "city_status_disagrees", "counts",
    "direction", "ranking_support", "skill_score", "matched_skills", "detected_skills",
    "retained_set", "unexpected_diagnostic", "overall_without_city", "blocking_reason", "short_circuit_reason",
])
def test_location_phase_rejects_noncity_or_unattributed_drift(phase_reports, tmp_path, defect):
    old, middle, fixed = phase_reports
    row = fixed["profiles"][0]
    decision = row["current_diagnostics"]["job-3"]
    noncity = next(item for item in decision["checks"] if item["dimension"] == "degree")
    if defect == "corpus": middle["corpus"]["judged_pairs"] += 1
    elif defect == "data": middle["fingerprints"]["data_files"] = {"changed": "hash"}
    elif defect == "profile": row["candidate"]["skills"] = ["Java"]
    elif defect == "label": row["label"] = "其他档案"
    elif defect == "baseline": row["systems"]["baseline"]["ranking"].reverse()
    elif defect == "source_scope": row["production_data_scope"]["total_records"] += 1
    elif defect == "limit": fixed["k"] += 1
    elif defect == "ranking_version": fixed["ranking_versions"] = ["changed-ranking"]
    elif defect == "diagnostic_keys": row["current_diagnostics"].pop("job-2")
    elif defect == "noncity_status": noncity["status"] = decision["predicted_conditions"]["degree"] = "met"
    elif defect == "noncity_reason": noncity["reason"] = "不同的解释"
    elif defect == "noncity_evidence": noncity["evidence"].append({"field": "title", "start": 0, "end": 1, "text": "假"})
    elif defect == "noncity_note": noncity["notes"].append("新增非城市规则")
    elif defect == "predicted_noncity": decision["predicted_conditions"]["degree"] = "met"
    elif defect == "duplicate_check": decision["checks"].append(copy.deepcopy(noncity))
    elif defect == "missing_check": decision["checks"].remove(noncity)
    elif defect == "city_status_disagrees": decision["predicted_conditions"]["city"] = "unknown"
    elif defect == "counts": row["production_counts"]["unknown"] += 1
    elif defect == "direction": decision["direction_fit"]["reason"] = "新方向判定"
    elif defect == "ranking_support": decision["ranking_support"]["reason"] = "新排序支持"
    elif defect in {"skill_score", "matched_skills", "detected_skills"}:
        item = row["systems"]["current"]["ranking"][0]
        item[defect] = .123 if defect == "skill_score" else ["C++"]
    elif defect == "retained_set": row["systems"]["current"]["ranking"] = []
    elif defect == "unexpected_diagnostic": decision["new_rule"] = True
    elif defect == "overall_without_city": decision["predicted_overall"] = "met"
    elif defect == "blocking_reason": row["current_diagnostics"]["job-2"]["blocking_reasons"] = []
    elif defect == "short_circuit_reason": decision["direction_not_assessed_reason"] = "qualification_or_closed_short_circuit"
    with pytest.raises(ValueError, match="[Ll]ocation|degree-only|profile|shared skill|frozen"):
        combine(tmp_path, phase_reports)


def test_city_release_cannot_leave_another_hard_condition_blocked(phase_reports, tmp_path):
    _, middle, fixed = phase_reports
    for report in (middle, fixed):
        city = city_check(report, "job-2")
        if report is middle:
            city.update(status="not_met", reason="合成城市限制")
            report["profiles"][0]["current_diagnostics"]["job-2"]["predicted_conditions"]["city"] = "not_met"
            report["profiles"][0]["current_diagnostics"]["job-2"]["blocking_reasons"].append("城市：合成城市限制")
    fixed["profiles"][0]["current_diagnostics"]["job-2"]["predicted_overall"] = "unknown"
    with pytest.raises(ValueError, match="[Ll]ocation|noncity"):
        combine(tmp_path, phase_reports)


def test_location_mode_requires_the_middle_run(phase_reports, tmp_path):
    with pytest.raises(ValueError, match="requires"):
        comparison.compare(tmp_path, previous=phase_reports[0], fixed=phase_reports[2], location_phase_baseline=True)


def test_cli_phase_flags_are_mutually_exclusive(tmp_path):
    with pytest.raises(SystemExit):
        comparison.main(["--dataset", str(tmp_path / "data"), "--json", str(tmp_path / "out.json"),
                         "--markdown", str(tmp_path / "out.md"), "--degree-only-baseline", "--location-phase-baseline"])


def test_cli_replay_cannot_run_location_phase(tmp_path):
    with pytest.raises(SystemExit):
        comparison.main(["--dataset", str(tmp_path / "data"), "--json", str(tmp_path / "out.json"),
                         "--markdown", str(tmp_path / "out.md"), "--replay-archive", "--location-phase-baseline"])


def test_cli_location_phase_selects_stage23_archive_and_existing_middle_manifest(phase_reports, monkeypatch, tmp_path):
    calls = []
    @contextmanager
    def archived(path):
        calls.append(("archive", path))
        yield path
    def version(directory, root, *, algorithm_manifest="algorithm_freeze.json"):
        calls.append(("run", root, algorithm_manifest))
        return copy.deepcopy(phase_reports[0])
    monkeypatch.setattr(comparison, "baseline_application", archived)
    monkeypatch.setattr(comparison, "run_version", version)
    output, markdown = tmp_path / "out.json", tmp_path / "out.md"
    comparison.main(["--dataset", str(tmp_path / "data"), "--baseline", "stage22", "--location-phase-baseline",
                     "--json", str(output), "--markdown", str(markdown)])
    assert ("archive", comparison.LOCATION_PHASE_BASELINE) in calls
    assert ("run", comparison.LOCATION_PHASE_BASELINE, "degree_only_algorithm_freeze.json") in calls
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["baseline_version"] == "stage22"
    assert "location_ablation_checks" in report
    assert "Stage 23" in markdown.read_text(encoding="utf-8")
