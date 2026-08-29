from typing import Any

import pytest
from pydantic import BaseModel, Field

from app.agent.contracts import (
    FinalAnswerResponse,
    ModelRequest,
    ToolCall,
    ToolCallResponse,
)
from app.agent.exceptions import (
    AgentError,
    AgentMaxStepsExceeded,
)
from app.agent.model_client import ModelClient
from app.agent.orchestrator import (
    AgentOrchestrator,
)
from app.agent.tools.base import BaseTool
from app.agent.tools.retrieval_tool import RetrieveJobKnowledgeTool
from app.agent.tools.registry import ToolRegistry
from app.rag.contracts import JobDocument, RetrievalResult
from app.rag.retriever import JobKnowledgeRetriever
from tests.agent.fakes.fake_model_client import (
    FakeModelClient,
)


class PositiveValueArguments(BaseModel):
    value: int = Field(
        gt=0,
    )


class RecordingTool(
    BaseTool[PositiveValueArguments]
):
    name = "record_value"
    description = "Record one positive integer value."
    args_schema = PositiveValueArguments

    def __init__(self) -> None:
        self.values: list[int] = []

    def _run(
        self,
        arguments: PositiveValueArguments,
    ) -> dict[str, int]:
        self.values.append(
            arguments.value
        )

        return {
            "value": arguments.value,
        }


class FailingTool(
    BaseTool[PositiveValueArguments]
):
    name = "failing_tool"
    description = "A test tool that always fails."
    args_schema = PositiveValueArguments

    def _run(
        self,
        arguments: PositiveValueArguments,
    ) -> Any:
        raise RuntimeError(
            "sensitive internal failure"
        )


class ExplodingModelClient(ModelClient):
    def generate(
        self,
        request: ModelRequest,
    ):
        raise RuntimeError(
            "model unavailable"
        )


class InvalidResponseModelClient(ModelClient):
    def generate(
        self,
        request: ModelRequest,
    ):
        return object()


class FakeJobKnowledgeRetriever(JobKnowledgeRetriever):
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def search(
        self,
        query: str,
        top_k: int,
    ) -> list[RetrievalResult]:
        self.calls.append((query, top_k))
        return [
            RetrievalResult(
                document=JobDocument(
                    id=7,
                    content="Agent workflow internship",
                    metadata={"job_id": 7},
                ),
                score=0.9,
            )
        ]


def build_registry(
    *tools: BaseTool[Any],
) -> ToolRegistry:
    registry = ToolRegistry()

    for tool in tools:
        registry.register(
            tool
        )

    return registry


def test_orchestrator_accepts_direct_final_answer() -> None:
    model = FakeModelClient(
        responses=[
            FinalAnswerResponse(
                answer="你好，我可以帮你查询岗位。"
            ),
        ]
    )

    orchestrator = AgentOrchestrator(
        model_client=model,
        tool_registry=ToolRegistry(),
    )

    result = orchestrator.run(
        "你好"
    )

    assert result.answer == (
        "你好，我可以帮你查询岗位。"
    )
    assert result.steps == 1
    assert result.tool_executions == []
    assert len(model.requests) == 1


def test_orchestrator_runs_tool_then_returns_final_answer() -> None:
    tool = RecordingTool()

    model = FakeModelClient(
        responses=[
            ToolCallResponse(
                tool_call=ToolCall(
                    call_id="call_001",
                    tool_name="record_value",
                    arguments={
                        "value": 3,
                    },
                )
            ),
            FinalAnswerResponse(
                answer="工具执行完成。"
            ),
        ]
    )

    orchestrator = AgentOrchestrator(
        model_client=model,
        tool_registry=build_registry(
            tool
        ),
    )

    result = orchestrator.run(
        "执行工具"
    )

    assert result.answer == (
        "工具执行完成。"
    )
    assert result.steps == 2
    assert len(
        result.tool_executions
    ) == 1
    assert tool.values == [3]

    execution = result.tool_executions[0]

    assert execution.call.tool_name == (
        "record_value"
    )
    assert execution.result.success is True
    assert execution.result.data == {
        "value": 3,
    }

    assert model.requests[0].tool_executions == []
    assert len(
        model.requests[1].tool_executions
    ) == 1
    assert (
        model.requests[1]
        .tool_executions[0]
        .result.data
        == {"value": 3}
    )


def test_orchestrator_runs_real_retrieval_tool_and_observes_result() -> None:
    retriever = FakeJobKnowledgeRetriever()
    retrieval_tool = RetrieveJobKnowledgeTool(retriever)
    model = FakeModelClient(
        responses=[
            ToolCallResponse(
                tool_call=ToolCall(
                    call_id="retrieve_001",
                    tool_name="retrieve_job_knowledge",
                    arguments={
                        "query": "agent workflow",
                        "top_k": 3,
                    },
                )
            ),
            FinalAnswerResponse(answer="已找到相关岗位知识。"),
        ]
    )

    result = AgentOrchestrator(
        model_client=model,
        tool_registry=build_registry(retrieval_tool),
    ).run("查找 agent workflow 相关岗位知识")

    assert result.answer == "已找到相关岗位知识。"
    assert result.steps == 2
    assert retriever.calls == [("agent workflow", 3)]
    assert len(result.tool_executions) == 1
    execution = result.tool_executions[0]
    assert execution.result.success is True
    assert execution.result.data == [
        {
            "document": {
                "id": 7,
                "content": "Agent workflow internship",
                "metadata": {"job_id": 7},
            },
            "score": 0.9,
        }
    ]
    assert model.requests[1].tool_executions[0] == execution


def test_orchestrator_runs_multiple_tools_in_sequence() -> None:
    tool = RecordingTool()

    model = FakeModelClient(
        responses=[
            ToolCallResponse(
                tool_call=ToolCall(
                    call_id="call_001",
                    tool_name="record_value",
                    arguments={
                        "value": 1,
                    },
                )
            ),
            ToolCallResponse(
                tool_call=ToolCall(
                    call_id="call_002",
                    tool_name="record_value",
                    arguments={
                        "value": 2,
                    },
                )
            ),
            FinalAnswerResponse(
                answer="两个工具步骤都完成了。"
            ),
        ]
    )

    orchestrator = AgentOrchestrator(
        model_client=model,
        tool_registry=build_registry(
            tool
        ),
    )

    result = orchestrator.run(
        "连续执行两次工具"
    )

    assert result.steps == 3
    assert tool.values == [
        1,
        2,
    ]
    assert len(
        result.tool_executions
    ) == 2

    assert [
        execution.call.call_id
        for execution
        in result.tool_executions
    ] == [
        "call_001",
        "call_002",
    ]

    assert len(
        model.requests[2].tool_executions
    ) == 2


def test_orchestrator_preserves_failed_tool_observation_for_correction() -> None:
    tool = RecordingTool()

    model = FakeModelClient(
        responses=[
            ToolCallResponse(
                tool_call=ToolCall(
                    call_id="call_001",
                    tool_name="record_value",
                    arguments={
                        "value": 0,
                    },
                )
            ),
            ToolCallResponse(
                tool_call=ToolCall(
                    call_id="call_002",
                    tool_name="record_value",
                    arguments={
                        "value": 1,
                    },
                )
            ),
            FinalAnswerResponse(
                answer="修正参数后执行成功。"
            ),
        ]
    )

    orchestrator = AgentOrchestrator(
        model_client=model,
        tool_registry=build_registry(
            tool
        ),
    )

    result = orchestrator.run(
        "测试参数修正"
    )

    assert result.steps == 3
    assert len(
        result.tool_executions
    ) == 2

    first_execution = (
        result.tool_executions[0]
    )
    second_execution = (
        result.tool_executions[1]
    )

    assert (
        first_execution.result.success
        is False
    )
    assert (
        first_execution.result.error
        is not None
    )
    assert (
        first_execution.result.error.startswith(
            "Invalid tool arguments:"
        )
    )

    assert (
        second_execution.result.success
        is True
    )
    assert tool.values == [1]

    assert len(
        model.requests[1].tool_executions
    ) == 1
    assert (
        model.requests[1]
        .tool_executions[0]
        .result.success
        is False
    )


def test_orchestrator_preserves_internal_tool_failure_as_observation() -> None:
    tool = FailingTool()

    model = FakeModelClient(
        responses=[
            ToolCallResponse(
                tool_call=ToolCall(
                    call_id="call_001",
                    tool_name="failing_tool",
                    arguments={
                        "value": 1,
                    },
                )
            ),
            FinalAnswerResponse(
                answer="我已经看到工具失败结果。"
            ),
        ]
    )

    orchestrator = AgentOrchestrator(
        model_client=model,
        tool_registry=build_registry(
            tool
        ),
    )

    result = orchestrator.run(
        "执行失败工具"
    )

    assert result.steps == 2
    assert len(
        result.tool_executions
    ) == 1

    execution = result.tool_executions[0]

    assert execution.result.success is False
    assert execution.result.error == (
        "Tool execution failed."
    )

    assert (
        model.requests[1]
        .tool_executions[0]
        .result.error
        == "Tool execution failed."
    )


def test_orchestrator_converts_unknown_tool_to_observation() -> None:
    model = FakeModelClient(
        responses=[
            ToolCallResponse(
                tool_call=ToolCall(
                    call_id="call_001",
                    tool_name="missing_tool",
                )
            ),
            FinalAnswerResponse(
                answer="我已改用可用能力。"
            ),
        ]
    )

    orchestrator = AgentOrchestrator(
        model_client=model,
        tool_registry=ToolRegistry(),
    )

    result = orchestrator.run(
        "调用一个不存在的工具"
    )

    assert result.steps == 2
    assert len(
        result.tool_executions
    ) == 1

    execution = result.tool_executions[0]

    assert execution.call.tool_name == (
        "missing_tool"
    )
    assert execution.result.success is False
    assert execution.result.error == (
        "Tool is not available."
    )

    assert (
        model.requests[1]
        .tool_executions[0]
        .result.error
        == "Tool is not available."
    )


def test_orchestrator_raises_when_max_steps_are_exhausted() -> None:
    tool = RecordingTool()

    model = FakeModelClient(
        responses=[
            ToolCallResponse(
                tool_call=ToolCall(
                    call_id="call_001",
                    tool_name="record_value",
                    arguments={
                        "value": 1,
                    },
                )
            ),
            ToolCallResponse(
                tool_call=ToolCall(
                    call_id="call_002",
                    tool_name="record_value",
                    arguments={
                        "value": 2,
                    },
                )
            ),
            FinalAnswerResponse(
                answer=(
                    "这个回答不应该被请求。"
                )
            ),
        ]
    )

    orchestrator = AgentOrchestrator(
        model_client=model,
        tool_registry=build_registry(
            tool
        ),
        max_steps=2,
    )

    with pytest.raises(
        AgentMaxStepsExceeded,
        match="maximum step limit of 2",
    ):
        orchestrator.run(
            "测试最大步骤限制"
        )

    assert len(model.requests) == 2
    assert tool.values == [
        1,
        2,
    ]


def test_orchestrator_rejects_invalid_max_steps() -> None:
    with pytest.raises(
        ValueError,
        match="max_steps",
    ):
        AgentOrchestrator(
            model_client=FakeModelClient(
                responses=[]
            ),
            tool_registry=ToolRegistry(),
            max_steps=0,
        )


@pytest.mark.parametrize(
    "user_message",
    [
        "",
        "   ",
        "\t\n",
    ],
)
def test_orchestrator_rejects_blank_user_message(
    user_message: str,
) -> None:
    model = FakeModelClient(
        responses=[
            FinalAnswerResponse(
                answer="不应该执行。"
            ),
        ]
    )

    orchestrator = AgentOrchestrator(
        model_client=model,
        tool_registry=ToolRegistry(),
    )

    with pytest.raises(
        ValueError,
        match="user_message cannot be blank",
    ):
        orchestrator.run(
            user_message
        )

    assert model.requests == []


def test_orchestrator_trims_user_message_before_model_request() -> None:
    model = FakeModelClient(
        responses=[
            FinalAnswerResponse(
                answer="完成。"
            ),
        ]
    )

    orchestrator = AgentOrchestrator(
        model_client=model,
        tool_registry=ToolRegistry(),
    )

    orchestrator.run(
        "   帮我找深圳岗位   "
    )

    assert (
        model.requests[0].user_message
        == "帮我找深圳岗位"
    )


def test_orchestrator_keeps_runs_isolated() -> None:
    tool = RecordingTool()

    model = FakeModelClient(
        responses=[
            ToolCallResponse(
                tool_call=ToolCall(
                    call_id="call_001",
                    tool_name="record_value",
                    arguments={
                        "value": 1,
                    },
                )
            ),
            FinalAnswerResponse(
                answer="第一次运行完成。"
            ),
            FinalAnswerResponse(
                answer="第二次运行完成。"
            ),
        ]
    )

    orchestrator = AgentOrchestrator(
        model_client=model,
        tool_registry=build_registry(
            tool
        ),
    )

    first_result = orchestrator.run(
        "第一次运行"
    )
    second_result = orchestrator.run(
        "第二次运行"
    )

    assert first_result.answer == (
        "第一次运行完成。"
    )
    assert first_result.steps == 2
    assert len(
        first_result.tool_executions
    ) == 1

    assert second_result.answer == (
        "第二次运行完成。"
    )
    assert second_result.steps == 1
    assert second_result.tool_executions == []

    assert len(model.requests) == 3
    assert (
        model.requests[2].user_message
        == "第二次运行"
    )
    assert (
        model.requests[2].tool_executions
        == []
    )

    assert tool.values == [
        1,
    ]


def test_orchestrator_propagates_model_client_error() -> None:
    orchestrator = AgentOrchestrator(
        model_client=ExplodingModelClient(),
        tool_registry=ToolRegistry(),
    )

    with pytest.raises(
        RuntimeError,
        match="model unavailable",
    ):
        orchestrator.run(
            "测试模型异常"
        )


def test_orchestrator_rejects_unsupported_model_response() -> None:
    orchestrator = AgentOrchestrator(
        model_client=InvalidResponseModelClient(),
        tool_registry=ToolRegistry(),
    )

    with pytest.raises(
        AgentError,
        match="Unsupported model response",
    ):
        orchestrator.run(
            "测试非法模型响应"
        )
