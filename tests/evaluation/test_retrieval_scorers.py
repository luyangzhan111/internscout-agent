import pytest

from evals.retrieval_contracts import (
    RetrievalEvalCase,
    RetrievalEvaluationCaseResult,
    RetrievalEvaluationRunResult,
)
from evals.retrieval_scorers import (
    HIT_AT_K,
    TOP_1_HIT,
    score_case,
    score_run,
)


def make_case(
    *,
    case_id: str = "retrieval_case",
    expected_job_id: int = 5,
    top_k: int = 3,
) -> RetrievalEvalCase:
    return RetrievalEvalCase(
        schema_version=1,
        case_id=case_id,
        description="Synthetic retrieval case.",
        query="synthetic query",
        top_k=top_k,
        expected_job_id=expected_job_id,
    )


def make_result(
    *,
    case_id: str = "retrieval_case",
    retrieved_job_ids: list[int] | None = None,
    status: str = "completed",
    error_type: str | None = None,
    error_message: str | None = None,
) -> RetrievalEvaluationCaseResult:
    return RetrievalEvaluationCaseResult(
        case_id=case_id,
        status=status,
        retrieved_job_ids=retrieved_job_ids or [],
        error_type=error_type,
        error_message=error_message,
    )


def make_run(
    results: list[RetrievalEvaluationCaseResult],
) -> RetrievalEvaluationRunResult:
    completed_count = sum(result.status == "completed" for result in results)
    return RetrievalEvaluationRunResult(
        case_results=results,
        completed_count=completed_count,
        failed_count=len(results) - completed_count,
    )


def metric(score, name: str):
    return next(item for item in score.metrics if item.name == name)


def test_case_top_one_passes_both_metrics() -> None:
    score = score_case(make_case(), make_result(retrieved_job_ids=[5, 2, 1]))

    assert score.status == "PASS"
    assert metric(score, HIT_AT_K).passed
    assert metric(score, TOP_1_HIT).passed


def test_case_target_in_top_k_but_not_top_one_fails_case() -> None:
    score = score_case(make_case(), make_result(retrieved_job_ids=[2, 5, 1]))

    assert score.status == "FAIL"
    assert metric(score, HIT_AT_K).passed
    assert not metric(score, TOP_1_HIT).passed


def test_case_target_outside_top_k_fails_hit_at_k() -> None:
    score = score_case(
        make_case(top_k=2),
        make_result(retrieved_job_ids=[2, 1, 5]),
    )

    assert score.status == "FAIL"
    assert not metric(score, HIT_AT_K).passed
    assert not metric(score, TOP_1_HIT).passed


def test_case_empty_results_fail_without_indexing_error() -> None:
    score = score_case(make_case(), make_result())

    assert score.status == "FAIL"
    assert not metric(score, HIT_AT_K).passed
    assert not metric(score, TOP_1_HIT).passed
    assert "retrieved results" in metric(score, HIT_AT_K).reason


def test_case_execution_failure_is_distinguished_from_wrong_ranking() -> None:
    score = score_case(
        make_case(),
        make_result(
            status="failed",
            error_type="RuntimeError",
            error_message="vector store unavailable",
        ),
    )

    assert score.status == "FAIL"
    assert all(not item.passed for item in score.metrics)
    assert all("Retrieval execution failed" in item.reason for item in score.metrics)
    assert all("vector store unavailable" in item.reason for item in score.metrics)


def test_run_all_cases_pass_with_one_rates() -> None:
    cases = [make_case(case_id="first"), make_case(case_id="second")]
    run = make_run([
        make_result(case_id="first", retrieved_job_ids=[5]),
        make_result(case_id="second", retrieved_job_ids=[5]),
    ])

    score = score_run(cases, run)

    assert score.status == "PASS"
    assert score.case_pass_rate == pytest.approx(1.0)
    assert score.hit_at_k_rate == pytest.approx(1.0)
    assert score.top_1_hit_rate == pytest.approx(1.0)
    assert score.failed_case_ids == []


def test_run_reports_failed_case_and_rates() -> None:
    cases = [make_case(case_id="first"), make_case(case_id="second")]
    run = make_run([
        make_result(case_id="first", retrieved_job_ids=[5]),
        make_result(case_id="second", retrieved_job_ids=[2, 5]),
    ])

    score = score_run(cases, run)

    assert score.status == "FAIL"
    assert score.failed_case_ids == ["second"]
    assert score.case_pass_rate == pytest.approx(0.5)
    assert score.hit_at_k_rate == pytest.approx(1.0)
    assert score.top_1_hit_rate == pytest.approx(0.5)


def test_run_reports_missing_case_result() -> None:
    score = score_run([make_case(case_id="missing")], make_run([]))

    assert score.status == "FAIL"
    assert score.missing_case_ids == ["missing"]
    assert score.failed_case_ids == ["missing"]
    assert any("Missing actual result" in error for error in score.alignment_errors)


def test_run_reports_unexpected_case_result() -> None:
    score = score_run(
        [make_case(case_id="expected")],
        make_run([make_result(case_id="unexpected", retrieved_job_ids=[5])]),
    )

    assert score.status == "FAIL"
    assert score.unexpected_case_ids == ["unexpected"]
    assert any("Unexpected actual case_id" in error for error in score.alignment_errors)


def test_run_reports_duplicate_actual_case_id() -> None:
    score = score_run(
        [make_case(case_id="duplicate")],
        make_run([
            make_result(case_id="duplicate", retrieved_job_ids=[5]),
            make_result(case_id="duplicate", retrieved_job_ids=[5]),
        ]),
    )

    assert score.status == "FAIL"
    assert any("Duplicate actual case_id" in error for error in score.alignment_errors)


def test_run_aligns_by_case_id_instead_of_list_position() -> None:
    cases = [
        make_case(case_id="first", expected_job_id=1),
        make_case(case_id="second", expected_job_id=2),
    ]
    run = make_run([
        make_result(case_id="second", retrieved_job_ids=[2]),
        make_result(case_id="first", retrieved_job_ids=[9]),
    ])

    score = score_run(cases, run)

    assert [case_score.case_id for case_score in score.case_scores] == [
        "first",
        "second",
    ]
    assert score.failed_case_ids == ["first"]
    assert score.case_scores[1].status == "PASS"


def test_run_empty_expected_cases_is_not_a_pass() -> None:
    score = score_run([], make_run([]))

    assert score.status == "FAIL"
    assert score.case_pass_rate == 0.0
    assert score.hit_at_k_rate == 0.0
    assert score.top_1_hit_rate == 0.0
