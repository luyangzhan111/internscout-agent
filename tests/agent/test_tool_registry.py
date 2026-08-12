from pydantic import BaseModel

import pytest

from app.agent.tools.base import BaseTool
from app.agent.tools.registry import ToolRegistry


class EmptyArguments(BaseModel):
    pass


class FirstTool(
    BaseTool[EmptyArguments]
):
    name = "first"
    description = "First test tool."
    args_schema = EmptyArguments

    def _run(
        self,
        arguments: EmptyArguments,
    ) -> str:
        return "first"


class SecondTool(
    BaseTool[EmptyArguments]
):
    name = "second"
    description = "Second test tool."
    args_schema = EmptyArguments

    def _run(
        self,
        arguments: EmptyArguments,
    ) -> str:
        return "second"


class DuplicateFirstTool(
    BaseTool[EmptyArguments]
):
    name = "first"
    description = "Duplicate first test tool."
    args_schema = EmptyArguments

    def _run(
        self,
        arguments: EmptyArguments,
    ) -> str:
        return "duplicate"


def test_registry_registers_and_returns_tool() -> None:
    registry = ToolRegistry()
    tool = FirstTool()

    registry.register(tool)

    assert registry.get("first") is tool


def test_registry_rejects_duplicate_tool_name() -> None:
    registry = ToolRegistry()

    registry.register(
        FirstTool()
    )

    with pytest.raises(
        ValueError,
        match="already registered",
    ):
        registry.register(
            DuplicateFirstTool()
        )


def test_registry_raises_for_unknown_tool() -> None:
    registry = ToolRegistry()

    with pytest.raises(
        KeyError,
        match="not registered",
    ):
        registry.get(
            "missing"
        )


def test_registry_lists_registered_tools() -> None:
    registry = ToolRegistry()
    first = FirstTool()
    second = SecondTool()

    registry.register(first)
    registry.register(second)

    assert registry.list_tools() == [
        first,
        second,
    ]


def test_registry_preserves_registration_order() -> None:
    registry = ToolRegistry()
    second = SecondTool()
    first = FirstTool()

    registry.register(second)
    registry.register(first)

    assert [
        tool.name
        for tool
        in registry.list_tools()
    ] == [
        "second",
        "first",
    ]