"""Blocking offline gate for Agent retrieval-tool integration."""

from collections.abc import Callable

from app.agent.contracts import (
    FinalAnswerResponse,
    ToolCall,
    ToolCallResponse,
)
from app.agent.tools.job_query import JobQueryPort
from app.schemas.job_response import JobRead
from evals.contracts import EvalCase, EvaluationScore
from evals.dataset import load_eval_cases
from evals.runner import EvaluationRunner
from evals.scorers import score_run
from tests.agent.fakes.fake_model_client import FakeModelClient
from tests.evaluation.retrieval_fixtures import build_controlled_retriever


_DATASET_PATH = "evals/cases/agent_retrieval_cases.jsonl"
_EXPECTED_CASE_IDS = (
    "agent_retrieval_ai_rag",
    "agent_retrieval_backend",
)


class RetrievalGateJobQuery(JobQueryPort):
    """Offline no-op query port required by Agent composition."""

    def search_jobs(
        self,
        *,
        city: str | None = None,
        company: str | None = None,
        skill: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[JobRead], int]:
        del city, company, skill, page, page_size
        return [], 0

    def get_job_by_id(self, job_id: int) -> JobRead | None:
        del job_id
        return None


def _final_answers() -> dict[str, str]:
    return {
        "agent_retrieval_ai_rag": "推荐 AI应用开发实习生，来自拓界智能。",
        "agent_retrieval_backend": "推荐 Python后端实习生，来自星河科技。",
    }


def _make_model_client_factory(
    clients: dict[str, FakeModelClient],
) -> Callable[[EvalCase], FakeModelClient]:
    def factory(case: EvalCase) -> FakeModelClient:
        expected_call = case.expected.tool_calls[0]
        client = FakeModelClient(
            responses=[
                ToolCallResponse(
                    tool_call=ToolCall(
                        call_id=f"gate-{case.case_id}",
                        tool_name=expected_call.tool_name,
                        arguments=expected_call.arguments,
                    )
                ),
                FinalAnswerResponse(answer=_final_answers()[case.case_id]),
            ]
        )
        clients[case.case_id] = client
        return client

    return factory


def _diagnostic_message(score: EvaluationScore) -> str:
    failed_case_scores = [
        {
            "case_id": case_score.case_id,
            "failure_reasons": case_score.failure_reasons,
        }
        for case_score in score.case_scores
        if not case_score.passed
    ]
    return (
        "Agent retrieval evaluation gate failed: "
        f"failed_case_ids={score.failed_case_ids}, "
        f"missing_case_ids={score.missing_case_ids}, "
        f"unexpected_case_ids={score.unexpected_case_ids}, "
        f"alignment_errors={score.alignment_errors}, "
        f"failures={failed_case_scores}"
    )


def test_agent_retrieval_evaluation_gate_passes() -> None:
    """Run scripted Agent retrieval calls through the real Agent loop."""

    cases = load_eval_cases(_DATASET_PATH)
    assert [case.case_id for case in cases] == list(_EXPECTED_CASE_IDS)
    assert all(case.category == "retrieval" for case in cases)

    clients: dict[str, FakeModelClient] = {}
    runner = EvaluationRunner(
        model_client_factory=_make_model_client_factory(clients),
        job_query_factory=lambda _: RetrievalGateJobQuery(),
        job_retriever_factory=lambda _: build_controlled_retriever(),
    )
    run = runner.run(_DATASET_PATH)
    score = score_run(cases, run)

    if not score.passed:
        raise AssertionError(_diagnostic_message(score))

    assert len(run.results) == 2
    assert score.total_cases == 2
    assert score.passed_cases == 2
    assert score.failed_cases == 0
    assert score.case_pass_rate == 1.0
    assert score.failed_case_ids == []

    for case in cases:
        requests = clients[case.case_id].requests
        assert len(requests) == 2
        second_request = requests[1]
        assert "retrieve_job_knowledge" in {
            tool.name for tool in second_request.tools
        }
        assert len(second_request.tool_executions) == 1
        execution = second_request.tool_executions[0]
        assert execution.call.tool_name == "retrieve_job_knowledge"
        assert execution.call.arguments == case.expected.tool_calls[0].arguments
        assert execution.result.success is True
        assert execution.result.data
        assert execution.result.data[0]["document"]["id"] == (
            case.expected.tool_results[0].data_assertions[0].equals
        )
