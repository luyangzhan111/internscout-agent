"""Execution runner for direct retrieval evaluation cases."""

from collections.abc import Iterable

from app.rag.retriever import JobKnowledgeRetriever

from evals.retrieval_contracts import (
    RetrievalEvalCase,
    RetrievalEvaluationCaseResult,
    RetrievalEvaluationRunResult,
)


class RetrievalEvaluationRunner:
    """Execute retrieval cases against an already composed production retriever."""

    def __init__(self, retriever: JobKnowledgeRetriever) -> None:
        self._retriever = retriever

    def run_case(
        self,
        case: RetrievalEvalCase,
    ) -> RetrievalEvaluationCaseResult:
        """Execute one case and retain either IDs or structured failure metadata."""

        try:
            results = self._retriever.search(
                case.query,
                top_k=case.top_k,
            )
            retrieved_job_ids = [result.document.id for result in results]
        except Exception as exc:
            return RetrievalEvaluationCaseResult(
                case_id=case.case_id,
                status="failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

        return RetrievalEvaluationCaseResult(
            case_id=case.case_id,
            status="completed",
            retrieved_job_ids=retrieved_job_ids,
        )

    def run(
        self,
        cases: Iterable[RetrievalEvalCase],
    ) -> RetrievalEvaluationRunResult:
        """Execute cases sequentially in the supplied dataset order."""

        case_results = [self.run_case(case) for case in cases]
        completed_count = sum(
            result.status == "completed" for result in case_results
        )
        return RetrievalEvaluationRunResult(
            case_results=case_results,
            completed_count=completed_count,
            failed_count=len(case_results) - completed_count,
        )


RetrievalRunner = RetrievalEvaluationRunner
