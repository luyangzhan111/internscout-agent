import pytest
from pydantic import ValidationError

from app.agent.contracts import (
    AgentResult,
    FinalAnswerResponse,
    ToolCall,
    ToolCallResponse,
    ToolExecution,
    ToolResult,
)


def test_tool_call_stores_name_id_and_arguments() -> None:
    tool_call = ToolCall(
        call_id="call_001",
        tool_name="search_jobs",
        arguments={
            "city": "深圳",
            "skill": "python",
        },
    )

    assert tool_call.call_id == "call_001"
    assert tool_call.tool_name == "search_jobs"
    assert tool_call.arguments == {
        "city": "深圳",
        "skill": "python",
    }


def test_tool_call_allows_empty_arguments() -> None:
    tool_call = ToolCall(
        call_id="call_001",
        tool_name="example_tool",
    )

    assert tool_call.arguments == {}


def test_successful_tool_result_is_valid() -> None:
    result = ToolResult(
        call_id="call_001",
        tool_name="search_jobs",
        success=True,
        data={
            "items": [],
            "total": 0,
        },
    )

    assert result.success is True
    assert result.data == {
        "items": [],
        "total": 0,
    }
    assert result.error is None


def test_failed_tool_result_is_valid_when_error_is_present() -> None:
    result = ToolResult(
        call_id="call_001",
        tool_name="search_jobs",
        success=False,
        error="database unavailable",
    )

    assert result.success is False
    assert result.data is None
    assert result.error == "database unavailable"


def test_successful_tool_result_rejects_error() -> None:
    with pytest.raises(
        ValidationError,
        match="A successful tool result cannot contain an error",
    ):
        ToolResult(
            call_id="call_001",
            tool_name="search_jobs",
            success=True,
            data={"items": []},
            error="unexpected error",
        )


@pytest.mark.parametrize(
    "error",
    [
        None,
        "",
        "   ",
    ],
)
def test_failed_tool_result_requires_error_message(
    error: str | None,
) -> None:
    with pytest.raises(
        ValidationError,
        match="A failed tool result must contain an error message",
    ):
        ToolResult(
            call_id="call_001",
            tool_name="search_jobs",
            success=False,
            error=error,
        )


def test_tool_execution_links_matching_call_and_result() -> None:
    tool_call = ToolCall(
        call_id="call_001",
        tool_name="search_jobs",
        arguments={"city": "深圳"},
    )
    result = ToolResult(
        call_id="call_001",
        tool_name="search_jobs",
        success=True,
        data={"items": []},
    )

    execution = ToolExecution(
        call=tool_call,
        result=result,
    )

    assert execution.call == tool_call
    assert execution.result == result


def test_tool_execution_rejects_mismatched_call_id() -> None:
    tool_call = ToolCall(
        call_id="call_001",
        tool_name="search_jobs",
    )
    result = ToolResult(
        call_id="call_002",
        tool_name="search_jobs",
        success=True,
    )

    with pytest.raises(
        ValidationError,
        match="Tool call and result must have the same call_id",
    ):
        ToolExecution(
            call=tool_call,
            result=result,
        )


def test_tool_execution_rejects_mismatched_tool_name() -> None:
    tool_call = ToolCall(
        call_id="call_001",
        tool_name="search_jobs",
    )
    result = ToolResult(
        call_id="call_001",
        tool_name="get_job_detail",
        success=True,
    )

    with pytest.raises(
        ValidationError,
        match="Tool call and result must have the same tool_name",
    ):
        ToolExecution(
            call=tool_call,
            result=result,
        )


def test_tool_call_response_has_tool_call_discriminator() -> None:
    response = ToolCallResponse(
        tool_call=ToolCall(
            call_id="call_001",
            tool_name="search_jobs",
            arguments={"city": "深圳"},
        )
    )

    assert response.type == "tool_call"
    assert response.tool_call.tool_name == "search_jobs"


def test_final_answer_response_has_final_answer_discriminator() -> None:
    response = FinalAnswerResponse(
        answer="找到 3 个符合条件的岗位。"
    )

    assert response.type == "final_answer"
    assert response.answer == "找到 3 个符合条件的岗位。"


def test_agent_result_stores_answer_steps_and_execution_trace() -> None:
    tool_call = ToolCall(
        call_id="call_001",
        tool_name="search_jobs",
        arguments={"city": "深圳"},
    )
    tool_result = ToolResult(
        call_id="call_001",
        tool_name="search_jobs",
        success=True,
        data={
            "items": [],
            "total": 0,
        },
    )
    execution = ToolExecution(
        call=tool_call,
        result=tool_result,
    )

    result = AgentResult(
        answer="当前没有找到符合条件的岗位。",
        tool_executions=[execution],
        steps=2,
    )

    assert result.answer == "当前没有找到符合条件的岗位。"
    assert result.steps == 2
    assert result.tool_executions == [execution]


def test_agent_result_rejects_negative_steps() -> None:
    with pytest.raises(ValidationError):
        AgentResult(
            answer="完成。",
            steps=-1,
        )