import pytest

from app.agent.contracts import (
    FinalAnswerResponse,
    ModelRequest,
    ToolCall,
    ToolCallResponse,
    ToolDefinition,
)
from app.agent.model_client import ModelClient
from tests.agent.fakes.fake_model_client import (
    FakeModelClient,
)


def test_model_client_is_abstract() -> None:
    with pytest.raises(TypeError):
        ModelClient()


def test_fake_model_returns_configured_responses_in_order() -> None:
    first_response = ToolCallResponse(
        tool_call=ToolCall(
            call_id="call_001",
            tool_name="search_jobs",
            arguments={
                "city": "深圳",
            },
        )
    )
    second_response = FinalAnswerResponse(
        answer="找到符合条件的岗位。"
    )

    client = FakeModelClient(
        responses=[
            first_response,
            second_response,
        ]
    )

    request = ModelRequest(
        user_message="帮我找深圳的实习岗位"
    )

    first_result = client.generate(
        request
    )
    second_result = client.generate(
        request
    )

    assert first_result == first_response
    assert second_result == second_response


def test_fake_model_records_request_snapshots() -> None:
    client = FakeModelClient(
        responses=[
            FinalAnswerResponse(
                answer="完成。"
            ),
        ]
    )

    request = ModelRequest(
        user_message="原始问题",
        tools=[
            ToolDefinition(
                name="search_jobs",
                description="Search stored jobs.",
                parameters={
                    "type": "object",
                },
            )
        ],
    )

    client.generate(
        request
    )

    request.user_message = "后来修改的问题"
    request.tools.clear()

    assert len(client.requests) == 1
    assert client.requests[0].user_message == (
        "原始问题"
    )
    assert len(
        client.requests[0].tools
    ) == 1
    assert (
        client.requests[0].tools[0].name
        == "search_jobs"
    )


def test_fake_model_returns_independent_response_copy() -> None:
    original_response = FinalAnswerResponse(
        answer="原始答案"
    )

    client = FakeModelClient(
        responses=[
            original_response,
        ]
    )

    returned_response = client.generate(
        ModelRequest(
            user_message="测试问题"
        )
    )

    returned_response.answer = "被修改后的答案"

    assert original_response.answer == (
        "原始答案"
    )


def test_fake_model_raises_when_responses_are_exhausted() -> None:
    client = FakeModelClient(
        responses=[
            FinalAnswerResponse(
                answer="唯一的回答"
            ),
        ]
    )

    request = ModelRequest(
        user_message="测试问题"
    )

    client.generate(
        request
    )

    with pytest.raises(
        RuntimeError,
        match="Fake model has no remaining responses",
    ):
        client.generate(
            request
        )