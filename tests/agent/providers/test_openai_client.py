from types import SimpleNamespace
from typing import Any

import pytest

from app.agent.contracts import (
    FinalAnswerResponse,
    ModelRequest,
    ToolCallResponse,
    ToolDefinition,
    ToolExecution,
    ToolResult,
    ToolCall,
)
from app.agent.providers.openai_client import OpenAIModelClient


class FakeResponses:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.responses = FakeResponses(response=response, error=error)


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


def test_rejects_non_empty_tool_execution_history() -> None:
    fake = FakeClient(response=response(output_text="不应请求"))
    execution = ToolExecution(
        call=ToolCall(call_id="call_001", tool_name="search_jobs"),
        result=ToolResult(
            call_id="call_001",
            tool_name="search_jobs",
            success=True,
            data={"jobs": []},
        ),
    )

    with pytest.raises(ValueError, match="tool execution history"):
        OpenAIModelClient(model="gpt-test", client=fake).generate(
            ModelRequest(user_message="继续", tool_executions=[execution])
        )

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
