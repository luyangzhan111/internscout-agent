"""Four-way comparisons must isolate ranking from qualification/retention."""
import copy
import json

import pytest

import evals.recommendation_comparison as comparison
from evals.recommendation_runner import run_dataset
from tests.evaluation.recruitment_corpus import REQUIRES_RECORDED_CORPUS
from tests.evaluation.test_recommendation_quality import tiny_dataset


def reports(monkeypatch):
    # A local immutable archive supplies synthetic metadata; no fake ablation
    # archive is published or used for the actual Stage22 evaluations.
    monkeypatch.setattr(comparison, "DEGREE_ONLY_BASELINE", comparison.BASELINES["stage21"])
    result = run_dataset(tiny_dataset())
    result["fingerprints"]["data_files"] = {"synthetic-fixture": "same-inputs"}
    return copy.deepcopy(result), copy.deepcopy(result), copy.deepcopy(result)


def test_four_way_report_keeps_degree_only_as_separate_system(monkeypatch, tmp_path):
    old, middle, fixed = reports(monkeypatch)
    fixed["profiles"][0]["current_diagnostics"]["job-3"]["ranking_support"] = {"reason": "合成排序说明"}
    report = comparison.compare(tmp_path, previous=old, fixed=fixed, degree_only=middle,
                                baseline=comparison.BASELINES["stage21"])
    assert report["versions"]["degree_only"] == middle
    assert report["summary"]["degree_only_recommender"] == middle["summary"]["current"]
    assert report["ranking_ablation_checks"][0]["same_complete_candidate_set"]
    assert report["ranking_ablation_checks"][0]["same_qualification_and_direction"]
    text = comparison.comparison_markdown(report)
    assert "Stage 22" in text and "四组" in text and "仅学历修复" in text


@pytest.mark.parametrize("defect", ["pool", "profile", "baseline", "count", "qualification", "direction", "retained_set"])
def test_ranking_ablation_cannot_hide_a_changed_pool_or_qualification(monkeypatch, tmp_path, defect):
    old, middle, fixed = reports(monkeypatch)
    row = fixed["profiles"][0]
    if defect == "pool": middle["fingerprints"]["data_files"] = {"changed": "checksum"}
    elif defect == "profile": middle["profiles"][0]["candidate"]["skills"] = ["C++"]
    elif defect == "baseline": middle["profiles"][0]["systems"]["baseline"]["top_k"] = []
    elif defect == "count": row["production_counts"]["unknown"] += 1
    elif defect == "qualification": row["current_diagnostics"]["job-3"]["predicted_conditions"]["degree"] = "not_met"
    elif defect == "direction": row["current_diagnostics"]["job-3"]["direction_fit"]["status"] = "uncertain"
    elif defect == "retained_set": row["systems"]["current"]["ranking"] = []
    with pytest.raises(ValueError, match="ablation|Ranking|candidate|qualifications"):
        comparison.compare(tmp_path, previous=old, fixed=fixed, degree_only=middle,
                           baseline=comparison.BASELINES["stage21"])


@REQUIRES_RECORDED_CORPUS
def test_stage21_archive_reproduces_original_profiles_after_new_rules_exist(tmp_path):
    directory = comparison.ROOT / "evals/cases/recommendation_quality_stage21_holdout26"
    output, markdown = tmp_path / "stage21.json", tmp_path / "stage21.md"
    comparison.main(["--dataset", str(directory), "--baseline", "stage21", "--replay-archive",
                     "--json", str(output), "--markdown", str(markdown)])
    actual = json.loads(output.read_text(encoding="utf-8"))
    original = json.loads((comparison.ROOT / "docs/evaluations/stage21-holdout.json").read_text(encoding="utf-8"))
    assert actual["profiles"] == original["versions"]["fixed"]["profiles"]
    assert actual["summary"]["current"] == original["summary"]["fixed_recommender"]
    assert actual["ranking_versions"] == ["direction-evidence-v3"]
    assert actual["eligibility_rules_versions"] == ["stage20-rules-v1"]


def test_replay_and_ablation_are_distinct_operations(tmp_path):
    with pytest.raises(SystemExit):
        comparison.main(["--dataset", str(tmp_path), "--json", str(tmp_path / "out.json"),
                         "--markdown", str(tmp_path / "out.md"), "--replay-archive", "--degree-only-baseline"])
