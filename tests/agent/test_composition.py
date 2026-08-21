import pytest

from app.agent.composition import create_agent_orchestrator
from app.agent.contracts import (
    FinalAnswerResponse,
    ModelRequest,
    ModelResponse,
    ToolCall,
    ToolCallResponse,
)
from app.agent.exceptions import AgentMaxStepsExceeded
from app.agent.orchestrator import AgentOrchestrator
from app.agent.tools.job_query import JobQueryPort
from app.schemas.job_response import JobRead
from tests.agent.fakes.fake_model_client import FakeModelClient


class FakeJobQuery(JobQueryPort):
    def search_jobs(
        self,
        *,
        city: str | None = None,
        company: str | None = None,
        skill: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[JobRead], int]:
        return [], 0

    def get_job_by_id(
        self,
        job_id: int,
    ) -> JobRead | None:
        return None


def create_orchestrator(
    responses: list[ModelResponse],
    *,
    max_steps: int = 5,
) -> tuple[AgentOrchestrator, FakeModelClient]:
    model_client = FakeModelClient(responses=responses)
    orchestrator = create_agent_orchestrator(
        model_client=model_client,
        job_query=FakeJobQuery(),
        max_steps=max_steps,
    )
    return orchestrator, model_client


def test_factory_creates_agent_orchestrator() -> None:
    orchestrator, _ = create_orchestrator(
        [FinalAnswerResponse(answer="完成。")]
    )

    assert isinstance(orchestrator, AgentOrchestrator)


def test_factory_preserves_tool_registration_order() -> None:
    orchestrator, _ = create_orchestrator(
        [FinalAnswerResponse(answer="完成。")]
    )

    result = orchestrator.run("查看可用工具")

    assert result.answer == "完成。"
    assert [
        definition.name
        for definition
        in orchestrator._tool_registry.list_definitions()
    ] == [
        "search_jobs",
        "get_job_detail",
        "match_jobs",
    ]


def test_factory_accepts_fake_model_client() -> None:
    orchestrator, model_client = create_orchestrator(
        [FinalAnswerResponse(answer="Fake Model 已注入。")]
    )

    result = orchestrator.run("测试 Fake Model")

    assert result.answer == "Fake Model 已注入。"
    assert len(model_client.requests) == 1
    assert [
        definition.name
        for definition
        in model_client.requests[0].tools
    ] == [
        "search_jobs",
        "get_job_detail",
        "match_jobs",
    ]


def test_factory_default_max_steps_is_five() -> None:
    responses: list[ModelResponse] = [
        ToolCallResponse(
            tool_call=ToolCall(
                call_id=f"call_{index}",
                tool_name="unavailable_tool",
                arguments={},
            )
        )
        for index
        in range(5)
    ]
    orchestrator, model_client = create_orchestrator(responses)

    with pytest.raises(
        AgentMaxStepsExceeded,
        match="maximum step limit of 5",
    ):
        orchestrator.run("测试默认最大步骤数")

    assert len(model_client.requests) == 5
