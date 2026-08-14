from app.agent.contracts import (
    ToolCall,
    ToolExecution,
    ToolResult,
)
from app.agent.state import AgentState


def test_agent_state_has_expected_initial_values() -> None:
    state = AgentState(
        user_message="帮我找深圳的 Python 实习岗位"
    )

    assert state.user_message == "帮我找深圳的 Python 实习岗位"
    assert state.step_count == 0
    assert state.tool_executions == []
    assert state.final_answer is None


def test_agent_state_can_update_runtime_values() -> None:
    state = AgentState(
        user_message="帮我找深圳的 Python 实习岗位"
    )

    state.step_count += 1
    state.final_answer = "找到 3 个符合条件的岗位。"

    assert state.step_count == 1
    assert state.final_answer == "找到 3 个符合条件的岗位。"


def test_agent_state_can_store_tool_execution() -> None:
    state = AgentState(
        user_message="帮我找深圳的 Python 实习岗位"
    )

    tool_call = ToolCall(
        call_id="call_001",
        tool_name="search_jobs",
        arguments={
            "city": "深圳",
            "skill": "python",
        },
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

    state.tool_executions.append(execution)

    assert state.tool_executions == [execution]


def test_agent_states_do_not_share_tool_execution_lists() -> None:
    first_state = AgentState(
        user_message="第一个请求"
    )
    second_state = AgentState(
        user_message="第二个请求"
    )

    execution = ToolExecution(
        call=ToolCall(
            call_id="call_001",
            tool_name="search_jobs",
        ),
        result=ToolResult(
            call_id="call_001",
            tool_name="search_jobs",
            success=True,
        ),
    )

    first_state.tool_executions.append(execution)

    assert first_state.tool_executions == [execution]
    assert second_state.tool_executions == []