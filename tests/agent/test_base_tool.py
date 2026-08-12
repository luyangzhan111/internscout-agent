from typing import Any

from pydantic import BaseModel, Field

from app.agent.contracts import ToolCall
from app.agent.tools.base import BaseTool


class DummyArguments(BaseModel):
    value: int = Field(
        gt=0,
    )


class DummyTool(
    BaseTool[DummyArguments]
):
    name = "dummy"
    description = "A test-only dummy tool."
    args_schema = DummyArguments

    def __init__(self) -> None:
        self.run_count = 0

    def _run(
        self,
        arguments: DummyArguments,
    ) -> dict[str, int]:
        self.run_count += 1

        return {
            "value": arguments.value,
        }


class FailingTool(
    BaseTool[DummyArguments]
):
    name = "failing"
    description = "A test-only failing tool."
    args_schema = DummyArguments

    def _run(
        self,
        arguments: DummyArguments,
    ) -> Any:
        raise RuntimeError(
            "sensitive internal database error"
        )


def test_base_tool_executes_valid_tool_call() -> None:
    tool = DummyTool()

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="dummy",
            arguments={
                "value": 3,
            },
        )
    )

    assert result.success is True
    assert result.data == {
        "value": 3,
    }
    assert result.error is None
    assert tool.run_count == 1


def test_base_tool_rejects_mismatched_tool_name() -> None:
    tool = DummyTool()

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="another_tool",
            arguments={
                "value": 3,
            },
        )
    )

    assert result.success is False
    assert result.error == (
        "Tool call name does not match "
        "the selected tool."
    )
    assert tool.run_count == 0


def test_base_tool_converts_argument_validation_failure() -> None:
    tool = DummyTool()

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="dummy",
            arguments={
                "value": 0,
            },
        )
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.startswith(
        "Invalid tool arguments:"
    )
    assert tool.run_count == 0


def test_base_tool_hides_internal_execution_error() -> None:
    tool = FailingTool()

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="failing",
            arguments={
                "value": 1,
            },
        )
    )

    assert result.success is False
    assert result.error == "Tool execution failed."
    assert "database" not in result.error
    assert "sensitive" not in result.error