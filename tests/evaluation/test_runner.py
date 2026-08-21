from app.agent.contracts import (
    FinalAnswerResponse,
    ModelResponse,
    ToolCall,
    ToolCallResponse,
)
from app.agent.tools.job_query import JobQueryPort
from app.schemas.job_response import JobRead
from evals.dataset import load_eval_cases
from evals.runner import EvaluationRunner
from tests.agent.fakes.fake_model_client import FakeModelClient


class FakeJobQuery(JobQueryPort):
    def __init__(self) -> None:
        self.search_calls: list[dict[str, object]] = []

    def search_jobs(
        self,
        *,
        city: str | None = None,
        company: str | None = None,
        skill: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[JobRead], int]:
        self.search_calls.append(
            {
                "city": city,
                "company": company,
                "skill": skill,
                "page": page,
                "page_size": page_size,
            }
        )
        return [], 0

    def get_job_by_id(
        self,
        job_id: int,
    ) -> JobRead | None:
        return None


def test_runner_executes_direct_final_answer_case() -> None:
    case = load_eval_cases()[0]

    runner = EvaluationRunner(
        model_client_factory=lambda _: FakeModelClient(
            responses=[FinalAnswerResponse(answer="执行完成。")]
        ),
        job_query_factory=lambda _: FakeJobQuery(),
    )

    result = runner.run_case(case)

    assert result.case_id == case.case_id
    assert result.status == "completed"
    assert result.agent_result is not None
    assert result.agent_result.answer == "执行完成。"
    assert result.agent_result.steps == 1
    assert result.error_type is None


def test_runner_executes_fake_model_tool_workflow() -> None:
    case = next(
        case
        for case in load_eval_cases()
        if case.case_id == "search_jobs_by_city_and_skill"
    )
    job_query = FakeJobQuery()
    responses: list[ModelResponse] = [
        ToolCallResponse(
            tool_call=ToolCall(
                call_id="eval_search_001",
                tool_name="search_jobs",
                arguments={
                    "city": "深圳",
                    "skill": "Python",
                },
            )
        ),
        FinalAnswerResponse(answer="已完成深圳 Python 岗位查询。"),
    ]

    runner = EvaluationRunner(
        model_client_factory=lambda _: FakeModelClient(responses=responses),
        job_query_factory=lambda _: job_query,
    )

    result = runner.run_case(case)

    assert result.status == "completed"
    assert result.agent_result is not None
    assert result.agent_result.steps == 2
    assert len(result.agent_result.tool_executions) == 1
    assert result.agent_result.tool_executions[0].result.success is True
    assert job_query.search_calls == [
        {
            "city": "深圳",
            "company": None,
            "skill": "Python",
            "page": 1,
            "page_size": 10,
        }
    ]


def test_runner_returns_structured_dataset_result() -> None:
    runner = EvaluationRunner(
        model_client_factory=lambda _: FakeModelClient(
            responses=[FinalAnswerResponse(answer="完成。")]
        ),
        job_query_factory=lambda _: FakeJobQuery(),
    )

    result = runner.run()

    assert result.total_cases == len(load_eval_cases())
    assert result.completed_cases == result.total_cases
    assert result.failed_cases == 0
    assert len(result.results) == result.total_cases
    assert {item.case_id for item in result.results} == {
        case.case_id
        for case in load_eval_cases()
    }
