"""Hard-exclusion safety must expose the cost of retaining all uncertainty."""

import pytest

from evals.recommendation_scorers import aggregate_direction_safety, score_direction_safety, score_ranking
from tests.evaluation.test_recommendation_quality import judgement


def decision(status=None, disposition=None):
    return {"direction_fit": {"status": status} if status else None,
            "disposition": disposition or ("direction_mismatch" if status == "unrelated" else "retained")}


def sample():
    labels = {
        "a": judgement("a", relevance=2),
        "b": judgement("b", relevance=1, direction="uncertain"),
        "c": judgement("c", relevance=0, direction="unrelated"),
        "d": judgement("d", relevance=0, direction="unrelated"),
        "e": judgement("e", relevance=3),
        "f": judgement("f", relevance=0, blocks=("degree",)),
        "g": judgement("g", relevance=1, direction="uncertain"),
    }
    diagnostics = {"a": decision("unrelated"), "b": decision("unrelated"), "c": decision("unrelated"),
                   "d": decision("uncertain"), "e": decision("uncertain"),
                   "f": decision(disposition="not_met"), "g": decision("uncertain")}
    return diagnostics, labels


def test_direction_safety_counts_have_explicit_assessed_and_pool_denominators():
    diagnostics, labels = sample()
    result = score_direction_safety(diagnostics, labels)
    assert result["targeted_pool_count"] == 7
    assert result["assessed_count"] == 6
    assert result["qualification_or_closed_skipped_count"] == 1
    assert result["gold_aligned_or_uncertain_pool_count"] == 5
    assert result["gold_aligned_or_uncertain_assessed_count"] == 4
    assert result["false_hard_excluded_aligned_count"] == 1
    assert result["false_hard_excluded_uncertain_count"] == 1
    assert result["false_hard_exclusion_assessed_rate"] == .5
    assert result["false_hard_exclusion_nonblocked_pool_rate"] == .5
    assert result["gold_unrelated_hard_exclusion_recall_assessed"] == .5
    assert result["retained_uncertain_count"] == 3
    assert result["retained_uncertain_weak_or_irrelevant_count"] == 2
    assert result["retained_uncertain_weak_or_irrelevant_rate"] == pytest.approx(2 / 3)
    assert result["retained_uncertain_gold_unrelated_count"] == 1
    assert result["false_hard_excluded_keys"] == ["a", "b"]


def test_all_uncertain_has_zero_wrong_hard_exclusions_but_zero_unrelated_filtering():
    diagnostics, labels = sample()
    all_uncertain = {key: decision("uncertain") if key != "f" else decision(disposition="not_met") for key in labels}
    result = score_direction_safety(all_uncertain, labels)
    assert result["false_hard_excluded_count"] == 0
    assert result["gold_unrelated_hard_exclusion_recall_assessed"] == 0
    assert result["retained_uncertain_count"] == 6
    assert result["retained_uncertain_weak_or_irrelevant_count"] == 4
    retained = {key for key in labels if key != "f"}
    ranking = score_ranking(list(retained), retained, labels)
    assert ranking["useful_retention_recall"] == 1
    assert ranking["precision_at_k"] < 1


def test_no_direction_decisions_are_na_rather_than_perfect_safety():
    result = score_direction_safety({"a": decision(disposition="not_met")},
                                    {"a": judgement("a", relevance=0, blocks=("degree",))})
    assert result["assessed_count"] == 0
    assert result["false_hard_exclusion_assessed_rate"] is None
    assert result["gold_unrelated_hard_exclusion_recall_assessed"] is None
    assert result["retained_uncertain_weak_or_irrelevant_rate"] is None


def test_no_requested_target_has_no_direction_denominator():
    result = score_direction_safety({"a": decision("not_requested")},
                                    {"a": judgement("a", direction="not_requested")})
    assert result["targeted_pool_count"] == 0
    assert result["assessed_count"] == 0
    assert result["false_hard_exclusion_assessed_rate"] is None


def test_aggregate_sums_pairs_and_recomputes_ratios():
    diagnostics, labels = sample()
    one = score_direction_safety(diagnostics, labels)
    result = aggregate_direction_safety([one, one])
    assert result["profile_count"] == 2
    assert result["assessed_count"] == 12
    assert result["false_hard_excluded_count"] == 4
    assert result["false_hard_exclusion_assessed_rate"] == .5
    assert result["retained_uncertain_count"] == 6


def test_missing_judgements_and_inconsistent_hard_decisions_are_rejected():
    diagnostics, labels = sample()
    with pytest.raises(ValueError):
        score_direction_safety({}, labels)
    diagnostics["a"] = decision("uncertain", "direction_mismatch")
    with pytest.raises(ValueError, match="require an unrelated"):
        score_direction_safety(diagnostics, labels)
    diagnostics["a"] = decision()
    with pytest.raises(ValueError, match="require a direction decision"):
        score_direction_safety(diagnostics, labels)
