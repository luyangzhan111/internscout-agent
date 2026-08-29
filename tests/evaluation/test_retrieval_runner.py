from dataclasses import dataclass

from app.rag.contracts import RetrievalResult
from app.rag.contracts import JobDocument
from evals.retrieval_contracts import RetrievalEvalCase
from evals.retrieval_runner import RetrievalEvaluationRunner


def make_case(
    *,
    case_id: str = "retrieval_case",
    query: str = "Python 后端",
    top_k: int = 3,
    expected_job_id: int = 1,
) -> RetrievalEvalCase:
    return RetrievalEvalCase(
        schema_version=1,
        case_id=case_id,
        description="Synthetic retrieval case.",
        query=query,
        top_k=top_k,
        expected_job_id=expected_job_id,
    )


def retrieval_results(*job_ids: int) -> list[RetrievalResult]:
    return [
        RetrievalResult(
            document=JobDocument(
                id=job_id,
                content=f"job {job_id}",
                metadata={"job_id": job_id},
            ),
            score=0.0,
        )
        for job_id in job_ids
    ]


@dataclass
class StubRetriever:
    results: list[RetrievalResult]
    error: Exception | None = None

    def __post_init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, top_k: int) -> list[RetrievalResult]:
        self.calls.append((query, top_k))
        if self.error is not None:
            raise self.error
        return self.results


def test_runner_passes_query_and_top_k_to_retriever() -> None:
    retriever = StubRetriever(retrieval_results(1))
    case = make_case(query="FastAPI 数据库", top_k=2)

    result = RetrievalEvaluationRunner(retriever).run_case(case)

    assert retriever.calls == [("FastAPI 数据库", 2)]
    assert result.status == "completed"


def test_runner_preserves_retrieval_result_order_and_ignores_scores() -> None:
    retriever = StubRetriever(retrieval_results(3, 1, 2))

    result = RetrievalEvaluationRunner(retriever).run_case(make_case())

    assert result.retrieved_job_ids == [3, 1, 2]


def test_expected_job_id_does_not_change_runner_execution() -> None:
    retriever = StubRetriever(retrieval_results(2, 1))
    runner = RetrievalEvaluationRunner(retriever)

    first = runner.run_case(make_case(expected_job_id=1))
    second = runner.run_case(make_case(expected_job_id=999))

    assert first.retrieved_job_ids == second.retrieved_job_ids
    assert retriever.calls == [("Python 后端", 3), ("Python 后端", 3)]


def test_runner_represents_empty_retrieval_as_completed_empty_result() -> None:
    result = RetrievalEvaluationRunner(StubRetriever([])).run_case(make_case())

    assert result.status == "completed"
    assert result.retrieved_job_ids == []
    assert result.error_type is None


def test_runner_captures_retriever_exception_as_case_failure() -> None:
    retriever = StubRetriever([], error=RuntimeError("retriever unavailable"))

    result = RetrievalEvaluationRunner(retriever).run_case(make_case())

    assert result.status == "failed"
    assert result.retrieved_job_ids == []
    assert result.error_type == "RuntimeError"
    assert result.error_message == "retriever unavailable"


def test_runner_executes_cases_sequentially_and_counts_outcomes() -> None:
    retriever = StubRetriever(retrieval_results(1))
    cases = [
        make_case(case_id="first", query="first"),
        make_case(case_id="second", query="second"),
    ]

    run = RetrievalEvaluationRunner(retriever).run(cases)

    assert [result.case_id for result in run.case_results] == ["first", "second"]
    assert retriever.calls == [("first", 3), ("second", 3)]
    assert run.completed_count == 2
    assert run.failed_count == 0


def test_runner_counts_failed_cases_in_run_result() -> None:
    retriever = StubRetriever(
        retrieval_results(1),
        error=ValueError("always fails"),
    )

    run = RetrievalEvaluationRunner(retriever).run([make_case()])

    assert run.completed_count == 0
    assert run.failed_count == 1


def test_runner_handles_empty_case_list() -> None:
    run = RetrievalEvaluationRunner(StubRetriever([])).run([])

    assert run.case_results == []
    assert run.completed_count == 0
    assert run.failed_count == 0
