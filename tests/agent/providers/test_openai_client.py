import json
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from app.agent.contracts import (
    AgentResult,
    FinalAnswerResponse,
    ModelRequest,
    ToolCallResponse,
    ToolDefinition,
    ToolExecution,
    ToolResult,
    ToolCall,
)
from app.agent.orchestrator import AgentOrchestrator
from app.agent.providers.openai_client import OpenAIModelClient
from app.agent.tools.base import BaseTool
from app.agent.tools.registry import ToolRegistry


class FakeResponses:
    def __init__(
        self,
        response: Any = None,
        error: Exception | None = None,
        responses: list[Any] | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        if self.responses is not None:
            return self.responses.pop(0)
        return self.response


class FakeClient:
    def __init__(
        self,
        response: Any = None,
        error: Exception | None = None,
        responses: list[Any] | None = None,
    ) -> None:
        self.responses = FakeResponses(
            response=response,
            error=error,
            responses=responses,
        )


def response(*, output_text: str = "", output: list[Any] | None = None) -> Any:
    return SimpleNamespace(output_text=output_text, output=output or [])


def function_call(
    *,
    call_id: str = "call_001",
    name: str = "search_jobs",
    arguments: str = '{"city": "深圳"}',
) -> Any:
    return SimpleNamespace(
        type="function_call",
        call_id=call_id,
        name=name,
        arguments=arguments,
    )


def execution(
    *,
    call_id: str = "call_001",
    tool_name: str = "search_jobs",
    arguments: dict[str, Any] | None = None,
    success: bool = True,
    data: Any = None,
    error: str | None = None,
) -> ToolExecution:
    return ToolExecution(
        call=ToolCall(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments or {"city": "深圳"},
        ),
        result=ToolResult(
            call_id=call_id,
            tool_name=tool_name,
            success=success,
            data=data,
            error=error,
        ),
    )


def test_constructor_requires_non_blank_model() -> None:
    with pytest.raises(ValueError, match="model cannot be blank"):
        OpenAIModelClient(model="", client=FakeClient())


def test_maps_final_answer_and_user_message() -> None:
    fake = FakeClient(response=response(output_text="可以帮你查询岗位。"))
    client = OpenAIModelClient(model="gpt-test", client=fake)

    result = client.generate(ModelRequest(user_message="帮我找岗位"))

    assert result == FinalAnswerResponse(answer="可以帮你查询岗位。")
    assert fake.responses.calls[0]["input"] == "帮我找岗位"
    assert fake.responses.calls[0]["model"] == "gpt-test"
    assert fake.responses.calls[0]["parallel_tool_calls"] is False


def test_maps_tool_definition_without_redefining_parameters() -> None:
    definition = ToolDefinition(
        name="search_jobs",
        description="Search stored jobs.",
        parameters={"type": "object", "properties": {"city": {"type": "string"}}},
    )
    fake = FakeClient(response=response(output_text="完成。"))
    OpenAIModelClient(model="gpt-test", client=fake).generate(
        ModelRequest(user_message="查询", tools=[definition])
    )

    assert fake.responses.calls[0]["tools"] == [
        {
            "type": "function",
            "name": "search_jobs",
            "description": "Search stored jobs.",
            "parameters": definition.parameters,
        }
    ]


def test_maps_single_tool_call_and_json_object_arguments() -> None:
    fake = FakeClient(response=response(output=[function_call()]))
    result = OpenAIModelClient(model="gpt-test", client=fake).generate(
        ModelRequest(user_message="查询深圳岗位")
    )

    assert result == ToolCallResponse(
        tool_call=ToolCall(
            call_id="call_001",
            tool_name="search_jobs",
            arguments={"city": "深圳"},
        )
    )


def test_rejects_invalid_json_arguments() -> None:
    fake = FakeClient(response=response(output=[function_call(arguments="not-json")]))
    with pytest.raises(ValueError):
        OpenAIModelClient(model="gpt-test", client=fake).generate(
            ModelRequest(user_message="查询")
        )


@pytest.mark.parametrize("arguments", ["[]", '"abc"', "1"])
def test_rejects_non_object_json_arguments(arguments: str) -> None:
    fake = FakeClient(response=response(output=[function_call(arguments=arguments)]))
    with pytest.raises(ValueError, match="JSON object"):
        OpenAIModelClient(model="gpt-test", client=fake).generate(
            ModelRequest(user_message="查询")
        )


def test_maps_successful_tool_execution_history() -> None:
    fake = FakeClient(response=response(output_text="继续。"))
    request = ModelRequest(
        user_message="查询深圳岗位",
        tool_executions=[
            execution(data={"items": [{"title": "后端实习"}], "total": 1})
        ],
    )

    OpenAIModelClient(model="gpt-test", client=fake).generate(request)

    input_items = fake.responses.calls[0]["input"]
    assert input_items[0] == {"role": "user", "content": "查询深圳岗位"}
    assert input_items[1] == {
        "type": "function_call",
        "call_id": "call_001",
        "name": "search_jobs",
        "arguments": '{"city": "深圳"}',
    }
    output_item = input_items[2]
    assert output_item["type"] == "function_call_output"
    assert output_item["call_id"] == "call_001"
    assert isinstance(output_item["output"], str)
    assert json.loads(output_item["output"]) == {
        "success": True,
        "tool_name": "search_jobs",
        "data": {"items": [{"title": "后端实习"}], "total": 1},
    }


def test_maps_failed_tool_execution_history() -> None:
    fake = FakeClient(response=response(output_text="请修正参数。"))
    request = ModelRequest(
        user_message="查询岗位",
        tool_executions=[
            execution(
                success=False,
                data=None,
                error="Invalid tool arguments: city is required",
            )
        ],
    )

    OpenAIModelClient(model="gpt-test", client=fake).generate(request)

    output = json.loads(fake.responses.calls[0]["input"][2]["output"])
    assert output == {
        "success": False,
        "tool_name": "search_jobs",
        "error": "Invalid tool arguments: city is required",
    }


def test_maps_multiple_tool_executions_in_order() -> None:
    fake = FakeClient(response=response(output_text="完成。"))
    request = ModelRequest(
        user_message="查询多个岗位",
        tool_executions=[
            execution(call_id="call_001", data={"total": 1}),
            execution(call_id="call_002", data={"total": 2}),
        ],
    )

    OpenAIModelClient(model="gpt-test", client=fake).generate(request)

    input_items = fake.responses.calls[0]["input"]
    assert [item.get("call_id") for item in input_items[1:]] == [
        "call_001",
        "call_001",
        "call_002",
        "call_002",
    ]
    assert [item["type"] for item in input_items[1:]] == [
        "function_call",
        "function_call_output",
        "function_call",
        "function_call_output",
    ]


def test_rejects_non_json_serializable_tool_history() -> None:
    fake = FakeClient(response=response(output_text="不应请求"))
    request = ModelRequest(
        user_message="查询",
        tool_executions=[execution(data={"invalid": object()})],
    )

    with pytest.raises(ValueError, match="JSON serializable"):
        OpenAIModelClient(model="gpt-test", client=fake).generate(request)

    assert fake.responses.calls == []


def test_propagates_provider_exception() -> None:
    fake = FakeClient(error=RuntimeError("provider unavailable"))
    with pytest.raises(RuntimeError, match="provider unavailable"):
        OpenAIModelClient(model="gpt-test", client=fake).generate(
            ModelRequest(user_message="查询")
        )


def test_rejects_multiple_function_calls() -> None:
    fake = FakeClient(response=response(output=[function_call(), function_call(call_id="call_002")]))
    with pytest.raises(ValueError, match="multiple function calls"):
        OpenAIModelClient(model="gpt-test", client=fake).generate(
            ModelRequest(user_message="查询")
        )


def test_rejects_mixed_function_call_and_final_text() -> None:
    fake = FakeClient(
        response=response(output_text="最终答案", output=[function_call()])
    )

    with pytest.raises(ValueError, match="both a function call and a final answer"):
        OpenAIModelClient(model="gpt-test", client=fake).generate(
            ModelRequest(user_message="查询")
        )


def test_rejects_empty_provider_output() -> None:
    fake = FakeClient(response=response())
    with pytest.raises(ValueError, match="final answer or function call"):
        OpenAIModelClient(model="gpt-test", client=fake).generate(
            ModelRequest(user_message="查询")
        )


class SearchArguments(BaseModel):
    city: str


class RecordingSearchTool(BaseTool[SearchArguments]):
    name = "search_jobs"
    description = "Search jobs."
    args_schema = SearchArguments

    def _run(self, arguments: SearchArguments) -> dict[str, Any]:
        return {"items": [{"city": arguments.city}], "total": 1}


def test_completes_offline_agent_loop_with_success_observation() -> None:
    fake = FakeClient(
        responses=[
            response(output=[function_call(arguments='{"city": "深圳"}')]),
            response(output_text="找到 1 个岗位。"),
        ]
    )
    registry = ToolRegistry()
    registry.register(RecordingSearchTool())

    result = AgentOrchestrator(
        model_client=OpenAIModelClient(model="gpt-test", client=fake),
        tool_registry=registry,
    ).run("查询深圳岗位")

    assert isinstance(result, AgentResult)
    assert result.answer == "找到 1 个岗位。"
    assert result.steps == 2
    assert len(result.tool_executions) == 1
    second_input = fake.responses.calls[1]["input"]
    assert second_input[1]["type"] == "function_call"
    assert second_input[2]["type"] == "function_call_output"
    assert json.loads(second_input[2]["output"]) == {
        "success": True,
        "tool_name": "search_jobs",
        "data": {"items": [{"city": "深圳"}], "total": 1},
    }


def test_completes_offline_agent_loop_with_failed_observation() -> None:
    fake = FakeClient(
        responses=[
            response(output=[function_call(arguments='{"city": 123}')]),
            response(output_text="参数无效，请重新查询。"),
        ]
    )
    registry = ToolRegistry()
    registry.register(RecordingSearchTool())

    result = AgentOrchestrator(
        model_client=OpenAIModelClient(model="gpt-test", client=fake),
        tool_registry=registry,
    ).run("查询岗位")

    assert result.answer == "参数无效，请重新查询。"
    assert result.steps == 2
    assert result.tool_executions[0].result.success is False
    second_output = json.loads(fake.responses.calls[1]["input"][2]["output"])
    assert second_output["success"] is False
    assert second_output["tool_name"] == "search_jobs"
    assert second_output["error"].startswith("Invalid tool arguments:")
    assert "city" in second_output["error"]
