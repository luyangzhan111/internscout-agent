"""Offline Agent Evaluation execution runner.

This module executes cases and records Agent results. It intentionally does
not compare results with expectations or calculate scores.
"""

from collections.abc import Callable
from pathlib import Path

from app.agent.composition import create_agent_orchestrator
from app.agent.model_client import ModelClient
from app.agent.tools.job_query import JobQueryPort
from app.rag.retriever import JobKnowledgeRetriever

from evals.contracts import (
    EvalCase,
    EvaluationCaseResult,
    EvaluationRunResult,
)
from evals.dataset import DEFAULT_DATASET_PATH, load_eval_cases


ModelClientFactory = Callable[[EvalCase], ModelClient]
JobQueryFactory = Callable[[EvalCase], JobQueryPort]
JobRetrieverFactory = Callable[
    [EvalCase],
    JobKnowledgeRetriever | None,
]


class EvaluationRunner:
    """Execute evaluation cases with injected offline dependencies."""

    def __init__(
        self,
        model_client_factory: ModelClientFactory,
        job_query_factory: JobQueryFactory,
        max_steps: int = 5,
        job_retriever_factory: JobRetrieverFactory | None = None,
    ) -> None:
        if max_steps < 1:
            raise ValueError(
                "max_steps must be greater than or equal to 1."
            )

        self._model_client_factory = model_client_factory
        self._job_query_factory = job_query_factory
        self._max_steps = max_steps
        self._job_retriever_factory = job_retriever_factory

    def run_case(
        self,
        case: EvalCase,
    ) -> EvaluationCaseResult:
        """Execute one case and capture either AgentResult or failure metadata."""

        model_client = self._model_client_factory(case)
        job_query = self._job_query_factory(case)
        retriever = (
            self._job_retriever_factory(case)
            if self._job_retriever_factory is not None
            else None
        )
        orchestrator = create_agent_orchestrator(
            model_client=model_client,
            job_query=job_query,
            max_steps=self._max_steps,
            job_retriever=retriever,
        )

        try:
            agent_result = orchestrator.run(case.user_message)
        except Exception as exc:
            return EvaluationCaseResult(
                case_id=case.case_id,
                status="failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

        return EvaluationCaseResult(
            case_id=case.case_id,
            status="completed",
            agent_result=agent_result,
        )

    def run(
        self,
        dataset_path: str | Path = DEFAULT_DATASET_PATH,
    ) -> EvaluationRunResult:
        """Load a JSONL dataset, execute all cases, and return raw results."""

        cases = load_eval_cases(dataset_path)
        results = [self.run_case(case) for case in cases]
        completed_cases = sum(
            result.status == "completed"
            for result in results
        )

        return EvaluationRunResult(
            dataset_path=str(Path(dataset_path)),
            results=results,
            total_cases=len(results),
            completed_cases=completed_cases,
            failed_cases=len(results) - completed_cases,
        )
