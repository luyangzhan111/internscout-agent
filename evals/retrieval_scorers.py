"""Deterministic ID-and-order scorers for direct retrieval evaluation."""

from collections.abc import Iterable

from evals.contracts import CaseScore, MetricResult
from evals.retrieval_contracts import (
    RetrievalEvalCase,
    RetrievalEvaluationCaseResult,
    RetrievalEvaluationRunResult,
    RetrievalEvaluationScore,
)


HIT_AT_K = "hit_at_k"
TOP_1_HIT = "top_1_hit"


def _metric(
    name: str,
    passed: bool,
    expected: object,
    actual: object,
    reason: str,
) -> MetricResult:
    return MetricResult(
        name=name,
        passed=passed,
        expected=expected,
        actual=actual,
        reason=reason,
    )


def _execution_failure_reason(result: RetrievalEvaluationCaseResult) -> str:
    error_type = result.error_type or "UnknownError"
    error_message = result.error_message or "No error message was recorded."
    return f"Retrieval execution failed with {error_type}: {error_message}"


def score_case(
    case: RetrievalEvalCase,
    result: RetrievalEvaluationCaseResult,
) -> CaseScore:
    """Score Hit@K and Top-1 using only retrieved IDs and their order."""

    if result.status != "completed":
        failure_reason = _execution_failure_reason(result)
        metrics = [
            _metric(HIT_AT_K, False, True, False, failure_reason),
            _metric(TOP_1_HIT, False, True, False, failure_reason),
        ]
    else:
        retrieved_job_ids = result.retrieved_job_ids
        top_k_ids = retrieved_job_ids[:case.top_k]
        hit_at_k = case.expected_job_id in top_k_ids
        top_1_hit = bool(retrieved_job_ids) and (
            retrieved_job_ids[0] == case.expected_job_id
        )
        metrics = [
            _metric(
                HIT_AT_K,
                hit_at_k,
                True,
                hit_at_k,
                (
                    "Expected job ID is present in the requested top-k."
                    if hit_at_k
                    else (
                        f"Expected job ID {case.expected_job_id} was not found "
                        f"in retrieved results[:{case.top_k}]."
                    )
                ),
            ),
            _metric(
                TOP_1_HIT,
                top_1_hit,
                True,
                top_1_hit,
                (
                    "Expected job ID is the top-1 result."
                    if top_1_hit
                    else (
                        f"Expected job ID {case.expected_job_id} was not the "
                        "top-1 result."
                    )
                ),
            ),
        ]

    failure_reasons = [
        f"{metric.name}: {metric.reason}"
        for metric in metrics
        if not metric.passed
    ]
    return CaseScore(
        case_id=case.case_id,
        status="PASS" if not failure_reasons else "FAIL",
        metrics=metrics,
        failure_reasons=failure_reasons,
    )


def score_run(
    cases: Iterable[RetrievalEvalCase],
    run: RetrievalEvaluationRunResult,
) -> RetrievalEvaluationScore:
    """Score expected and actual cases by case ID, reporting alignment errors."""

    expected_cases = list(cases)
    expected_by_id: dict[str, RetrievalEvalCase] = {}
    alignment_errors: list[str] = []
    for case in expected_cases:
        if case.case_id in expected_by_id:
            alignment_errors.append(
                f"Duplicate expected case_id {case.case_id!r}."
            )
        expected_by_id.setdefault(case.case_id, case)

    actual_by_id: dict[str, RetrievalEvaluationCaseResult] = {}
    for result in run.case_results:
        if result.case_id in actual_by_id:
            alignment_errors.append(
                f"Duplicate actual case_id {result.case_id!r}."
            )
        actual_by_id.setdefault(result.case_id, result)

    missing_case_ids = [
        case.case_id
        for case in expected_cases
        if case.case_id not in actual_by_id
    ]
    unexpected_case_ids = sorted(
        set(actual_by_id) - set(expected_by_id)
    )
    alignment_errors.extend(
        f"Missing actual result for case_id {case_id!r}."
        for case_id in missing_case_ids
    )
    alignment_errors.extend(
        f"Unexpected actual case_id {case_id!r}."
        for case_id in unexpected_case_ids
    )

    case_scores: list[CaseScore] = []
    for case in expected_cases:
        actual_result = actual_by_id.get(case.case_id)
        if actual_result is None:
            actual_result = RetrievalEvaluationCaseResult(
                case_id=case.case_id,
                status="failed",
                error_type="MissingEvaluationResult",
                error_message="No actual result was supplied for this case.",
            )
        case_scores.append(score_case(case, actual_result))

    total_cases = len(case_scores)
    passed_cases = sum(case_score.passed for case_score in case_scores)
    failed_cases = total_cases - passed_cases
    failed_case_ids = [
        case_score.case_id
        for case_score in case_scores
        if not case_score.passed
    ]

    hit_at_k_passed = sum(
        metric.passed
        for case_score in case_scores
        for metric in case_score.metrics
        if metric.name == HIT_AT_K
    )
    top_1_hit_passed = sum(
        metric.passed
        for case_score in case_scores
        for metric in case_score.metrics
        if metric.name == TOP_1_HIT
    )
    case_pass_rate = passed_cases / total_cases if total_cases else 0.0
    hit_at_k_rate = hit_at_k_passed / total_cases if total_cases else 0.0
    top_1_hit_rate = top_1_hit_passed / total_cases if total_cases else 0.0
    fully_passed = (
        total_cases > 0
        and not failed_case_ids
        and not alignment_errors
    )

    return RetrievalEvaluationScore(
        total_cases=total_cases,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        case_pass_rate=case_pass_rate,
        hit_at_k_rate=hit_at_k_rate,
        top_1_hit_rate=top_1_hit_rate,
        failed_case_ids=failed_case_ids,
        case_scores=case_scores,
        missing_case_ids=missing_case_ids,
        unexpected_case_ids=unexpected_case_ids,
        alignment_errors=alignment_errors,
        status="PASS" if fully_passed else "FAIL",
    )


score_retrieval_case = score_case
score_retrieval_run = score_run
