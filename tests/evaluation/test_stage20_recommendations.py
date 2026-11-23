"""Keep old regressions and the new, pre-ranked holdout separate and immutable."""

from collections import Counter
import json
from pathlib import Path
import pytest

from evals.recommendation_dataset import load_dataset
from evals.recommendation_comparison import BASELINES, baseline_application, run_version
from tests.evaluation.recruitment_corpus import REQUIRES_RECORDED_CORPUS


ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "evals/cases/recommendation_quality"
REGRESSION = ROOT / "evals/cases/recommendation_quality_stage20_regression"
HOLDOUT = ROOT / "evals/cases/recommendation_quality_stage20"
pytestmark = REQUIRES_RECORDED_CORPUS


@pytest.fixture(scope="module")
def stage20_root():
    with baseline_application(BASELINES["stage20"]) as archived:
        yield archived


def test_old_labels_are_reused_exactly_and_target_regressions_are_recovered(stage20_root):
    for name in ("jobs.jsonl", "gold.jsonl", "profiles.json"):
        assert (REGRESSION / name).read_bytes() == (OLD / name).read_bytes()
    dataset = load_dataset(REGRESSION, algorithm_root=stage20_root)
    report = run_version(REGRESSION, stage20_root)
    targets = {"ai-campus": ("byte-ai-multimodal-backend", "byte-backend-ad", "byte-backend-commerce"),
               "cv-campus": ("byte-ai-multimodal-backend",)}
    for profile in report["profiles"]:
        for key in targets.get(profile["profile_id"], ()):
            assert profile["current_diagnostics"][key]["disposition"] == "retained"
    degree = report["eligibility_agreement"]["dimensions"]["degree"]
    assert degree["correct"] == degree["total"] == 180
    original = json.loads((ROOT / "docs/evaluations/stage19-results.json").read_text(encoding="utf-8"))
    assert original["summary"]["current"]["false_excluded_useful_pairs"] == 4


def test_new_holdout_coverage_and_profiles_do_not_reuse_old_job_identities(stage20_root):
    old = load_dataset(REGRESSION, algorithm_root=stage20_root)
    new = load_dataset(HOLDOUT, algorithm_root=stage20_root)
    assert len(new.primary) >= 24
    assert len(new.profiles) == 8
    assert len(new.gold) == len(new.primary) * 8
    assert [p.model_dump() for p in new.profiles[:6]] == [p.model_dump() for p in old.profiles]
    assert all(p.candidate.conditions.degree == "master" and p.candidate.conditions.degree_status == "enrolled"
               for p in new.profiles[6:])
    assert not {j.source_url for j in old.primary.values()} & {j.source_url for j in new.primary.values()}
    assert not {j.source_job_id for j in old.primary.values()} & {j.source_job_id for j in new.primary.values()}
    counts = Counter(r.metadata["collection_direction"] for r in new.records)
    assert all(counts[direction] >= 6 for direction in ("ai_application", "backend", "computer_vision"))
    assert counts["other"] >= 3


def test_new_data_result_is_reproducible_without_imposing_an_improvement_threshold(stage20_root):
    current = run_version(HOLDOUT, stage20_root)
    saved = json.loads((ROOT / "docs/evaluations/stage20-holdout.json").read_text(encoding="utf-8"))
    assert current["summary"]["current"] == saved["summary"]["fixed_recommender"]
    assert current["profiles"] == saved["versions"]["fixed"]["profiles"]
    assert current["summary"]["baseline"] == saved["summary"]["skill_baseline"]
    assert current["corpus"]["judged_pairs"] == 192
    assert sum(len(p["current_diagnostics"]) for p in current["profiles"]) == 192
