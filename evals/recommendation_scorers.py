"""Small, explicit metrics for a fixed candidate-by-job recommendation pool."""

from math import log2

from evals.recommendation_dataset import Gold


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def score_ranking(
    ordered: list[str], retained: set[str], judgements: dict[str, Gold], *, k: int = 5,
) -> dict:
    """Score only frozen labels; an empty result cannot improve P@K.

    Exclusion recall uses the whole retained set. A relevant job below the
    display cutoff is not a false exclusion. Missing display slots contribute
    zero gain. Queries without any gain have undefined nDCG, reported as null.
    """
    if type(k) is not int or k < 1:
        raise ValueError("k must be a positive integer")
    if len(ordered) != len(set(ordered)) or set(ordered) != retained:
        raise ValueError("Ranking must contain each retained job exactly once")
    if not retained.issubset(judgements):
        raise ValueError("Every ranked job needs a judgement")
    top = ordered[:k]
    positives = {key for key, g in judgements.items() if g.relevance >= 2}
    useful = {key for key in positives if judgements[key].overall != "not_met"
              and judgements[key].direction != "unrelated"}
    strict = {key for key in useful if judgements[key].overall == "met"}
    missed = useful - retained
    wrong_direction = [key for key in top if judgements[key].direction == "unrelated"]
    wrong_conditions = [key for key in top if judgements[key].overall == "not_met"]
    bad = set(wrong_direction) | set(wrong_conditions)
    dcg = sum((2 ** judgements[key].relevance - 1) / log2(index + 2)
              for index, key in enumerate(top))
    ideal = sorted((g.relevance for g in judgements.values()), reverse=True)[:k]
    idcg = sum((2 ** rel - 1) / log2(index + 2) for index, rel in enumerate(ideal))
    return {
        "k": k, "returned": len(top), "retained": len(retained),
        "relevant_in_top_k": sum(key in positives for key in top),
        "precision_denominator": k,
        "precision_at_k": sum(key in positives for key in top) / k,
        "maximum_precision_at_k": min(k, len(positives)) / k,
        "display_fill_rate": len(top) / k,
        "ndcg_at_k": dcg / idcg if idcg else None,
        "dcg_at_k": dcg, "ideal_dcg_at_k": idcg,
        "relevant_pool_count": len(positives),
        "wrong_direction_in_top_k": len(wrong_direction),
        "wrong_conditions_in_top_k": len(wrong_conditions),
        "clearly_wrong_in_top_k": len(bad),
        "clearly_wrong_returned_rate": ratio(len(bad), len(top)),
        "clearly_wrong_slots_rate": len(bad) / k,
        "useful_pool_count": len(useful),
        "false_excluded_useful_count": len(missed),
        "false_excluded_useful_rate": ratio(len(missed), len(useful)),
        "useful_retention_recall": ratio(len(useful & retained), len(useful)),
        "strict_met_useful_count": len(strict),
        "strict_met_false_excluded_count": len(strict - retained),
        "strict_met_false_excluded_rate": ratio(len(strict - retained), len(strict)),
        "missed_useful_keys": sorted(missed),
        "relevant_below_top_k": sorted((positives & retained) - set(top)),
        "no_relevant_intent": not positives,
        "correct_empty_for_no_relevant": not retained if not positives else None,
    }


def aggregate_metrics(items: list[dict]) -> dict:
    """Report query macro scores and pooled integer counts with denominators."""
    if not items:
        raise ValueError("At least one intent is required")
    valid_ndcg = [m["ndcg_at_k"] for m in items if m["ndcg_at_k"] is not None]
    with_relevant = [m for m in items if not m["no_relevant_intent"]]
    sum_of = lambda name: sum(m[name] for m in items)
    slots, returned = sum_of("precision_denominator"), sum_of("returned")
    useful, missed = sum_of("useful_pool_count"), sum_of("false_excluded_useful_count")
    strict, strict_missed = sum_of("strict_met_useful_count"), sum_of("strict_met_false_excluded_count")
    return {
        "intent_count": len(items), "display_slots": slots,
        "returned": returned, "relevant_in_top_k": sum_of("relevant_in_top_k"),
        "precision_at_k_macro": sum(m["precision_at_k"] for m in items) / len(items),
        "maximum_precision_at_k_macro": sum(m["maximum_precision_at_k"] for m in items) / len(items),
        "precision_at_k_micro": sum_of("relevant_in_top_k") / slots,
        "precision_at_k_relevant_intents_macro": (
            sum(m["precision_at_k"] for m in with_relevant) / len(with_relevant) if with_relevant else None
        ),
        "ndcg_at_k_macro": sum(valid_ndcg) / len(valid_ndcg) if valid_ndcg else None,
        "ndcg_intent_denominator": len(valid_ndcg),
        "no_relevant_intents": len(items) - len(with_relevant),
        "correct_empty_no_relevant_intents": sum(m["correct_empty_for_no_relevant"] is True for m in items),
        "display_fill_rate": returned / slots,
        "wrong_direction_in_top_k": sum_of("wrong_direction_in_top_k"),
        "wrong_conditions_in_top_k": sum_of("wrong_conditions_in_top_k"),
        "clearly_wrong_in_top_k": sum_of("clearly_wrong_in_top_k"),
        "clearly_wrong_returned_rate": ratio(sum_of("clearly_wrong_in_top_k"), returned),
        "clearly_wrong_slots_rate": sum_of("clearly_wrong_in_top_k") / slots,
        "useful_pool_pairs": useful, "false_excluded_useful_pairs": missed,
        "false_excluded_useful_rate": ratio(missed, useful),
        "useful_retention_recall": ratio(useful - missed, useful),
        "strict_met_useful_pairs": strict, "strict_met_false_excluded_pairs": strict_missed,
        "strict_met_false_excluded_rate": ratio(strict_missed, strict),
    }


def _direction_rates(counts: dict) -> dict:
    return {
        "false_hard_exclusion_assessed_rate": ratio(counts["false_hard_excluded_count"], counts["gold_aligned_or_uncertain_assessed_count"]),
        "false_hard_exclusion_nonblocked_pool_rate": ratio(counts["false_hard_excluded_nonblocked_count"], counts["gold_nonblocked_aligned_or_uncertain_pool_count"]),
        "gold_unrelated_hard_exclusion_recall_assessed": ratio(counts["correctly_hard_excluded_unrelated_count"], counts["gold_unrelated_assessed_count"]),
        "retained_uncertain_weak_or_irrelevant_rate": ratio(counts["retained_uncertain_weak_or_irrelevant_count"], counts["retained_uncertain_count"]),
        "retained_uncertain_gold_unrelated_rate": ratio(counts["retained_uncertain_gold_unrelated_count"], counts["retained_uncertain_count"]),
    }


def score_direction_safety(diagnostics: dict[str, dict], judgements: dict[str, Gold]) -> dict:
    """Separate unsafe hard exclusion from the cost of retaining uncertainty.

    Qualification short circuits never count as direction decisions. Report
    both assessed denominators and the complete gold-nonblocked pool, so a
    rule that marks everything uncertain cannot look good on one number alone.
    """
    if set(diagnostics) != set(judgements):
        raise ValueError("Direction safety requires every frozen candidate-job judgement")
    scope = {key for key, g in judgements.items() if g.direction != "not_requested"}
    assessed = set()
    hard, uncertain = set(), set()
    for key, decision in diagnostics.items():
        fit = decision.get("direction_fit")
        status = fit.get("status") if fit is not None else None
        if status is None and decision["disposition"] not in {"not_met", "closed"}:
            raise ValueError("Retained or direction-excluded jobs require a direction decision")
        if status is not None and status not in {"aligned", "uncertain", "unrelated", "not_requested"}:
            raise ValueError("Unsupported production direction status")
        if key in scope and status in {"aligned", "uncertain", "unrelated"}:
            assessed.add(key)
        if decision["disposition"] == "direction_mismatch":
            if status != "unrelated":
                raise ValueError("Hard direction exclusions require an unrelated production decision")
            hard.add(key)
        if key in scope and decision["disposition"] == "retained" and status == "uncertain":
            uncertain.add(key)
    nonunrelated = {key for key in scope if judgements[key].direction in {"aligned", "uncertain"}}
    gold_aligned = {key for key in scope if judgements[key].direction == "aligned"}
    gold_uncertain = {key for key in scope if judgements[key].direction == "uncertain"}
    gold_unrelated = {key for key in scope if judgements[key].direction == "unrelated"}
    nonblocked = {key for key in scope if judgements[key].overall != "not_met"}
    false = hard & nonunrelated
    weak = {key for key in uncertain if judgements[key].relevance < 2}
    counts = {
        "targeted_pool_count": len(scope), "assessed_count": len(assessed),
        "qualification_or_closed_skipped_count": len(scope - assessed),
        "gold_aligned_or_uncertain_pool_count": len(nonunrelated),
        "gold_aligned_or_uncertain_assessed_count": len(nonunrelated & assessed),
        "gold_nonblocked_aligned_or_uncertain_pool_count": len(nonunrelated & nonblocked),
        "false_hard_excluded_aligned_count": len(false & gold_aligned),
        "false_hard_excluded_uncertain_count": len(false & gold_uncertain),
        "false_hard_excluded_count": len(false),
        "false_hard_excluded_nonblocked_count": len(false & nonblocked),
        "gold_unrelated_assessed_count": len(gold_unrelated & assessed),
        "correctly_hard_excluded_unrelated_count": len(hard & gold_unrelated),
        "retained_uncertain_count": len(uncertain),
        "retained_uncertain_gold_aligned_count": len(uncertain & gold_aligned),
        "retained_uncertain_gold_uncertain_count": len(uncertain & gold_uncertain),
        "retained_uncertain_gold_unrelated_count": len(uncertain & gold_unrelated),
        "retained_uncertain_weak_or_irrelevant_count": len(weak),
        "retained_uncertain_relevant_count": len(uncertain - weak),
    }
    return {**counts, **_direction_rates(counts),
            "false_hard_excluded_keys": sorted(false),
            "retained_uncertain_weak_or_irrelevant_keys": sorted(weak)}


def aggregate_direction_safety(items: list[dict]) -> dict:
    if not items:
        raise ValueError("At least one intent is required for direction safety")
    counters = {key for key in items[0] if key.endswith("_count")}
    if any({key for key in item if key.endswith("_count")} != counters for item in items):
        raise ValueError("Direction safety counters must use the same schema")
    counts = {key: sum(item[key] for item in items) for key in sorted(counters)}
    return {"profile_count": len(items), **counts, **_direction_rates(counts)}
