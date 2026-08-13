from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.agent.contracts import (
    ToolCall,
    ToolDefinition,
    ToolResult,
)


ArgumentsT = TypeVar(
    "ArgumentsT",
    bound=BaseModel,
)


class BaseTool(ABC, Generic[ArgumentsT]):
    """Base contract shared by all registered agent tools."""

    name: str
    description: str
    args_schema: type[ArgumentsT]

    def definition(self) -> ToolDefinition:
        """Return the provider-neutral definition exposed to models."""

        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.args_schema.model_json_schema(),
        )

    def execute(
        self,
        tool_call: ToolCall,
    ) -> ToolResult:
        """
        Validate and execute one tool call.

        Model-provided arguments are validated before business logic runs.
        Validation failures and internal execution failures are converted
        into controlled ToolResult objects.
        """

        if tool_call.tool_name != self.name:
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=False,
                error=(
                    "Tool call name does not match "
                    "the selected tool."
                ),
            )

        try:
            arguments = self.args_schema.model_validate(
                tool_call.arguments
            )
        except ValidationError as exc:
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=self.name,
                success=False,
                error=(
                    "Invalid tool arguments: "
                    f"{exc}"
                ),
            )

        try:
            data = self._run(arguments)
        except Exception:
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=self.name,
                success=False,
                error="Tool execution failed.",
            )

        return ToolResult(
            call_id=tool_call.call_id,
            tool_name=self.name,
            success=True,
            data=data,
        )

    @abstractmethod
    def _run(
        self,
        arguments: ArgumentsT,
    ) -> Any:
        """Execute validated tool-specific business logic."""