from typing import Any, Literal, TypeAlias

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)


class ToolDefinition(BaseModel):
    """Provider-neutral description of one available agent tool."""

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(
        default_factory=dict
    )


class ToolCall(BaseModel):
    """A model request to execute one registered agent tool."""

    call_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(
        default_factory=dict
    )


class ToolResult(BaseModel):
    """The result produced by executing a tool call."""

    call_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    success: bool
    data: Any | None = None
    error: str | None = None

    @model_validator(mode="after")
    def validate_result_state(self) -> "ToolResult":
        if self.success and self.error is not None:
            raise ValueError(
                "A successful tool result cannot contain an error."
            )

        if not self.success:
            if self.error is None or not self.error.strip():
                raise ValueError(
                    "A failed tool result must contain an error message."
                )

        return self


class ToolExecution(BaseModel):
    """A complete execution trace linking one tool call to its result."""

    call: ToolCall
    result: ToolResult

    @model_validator(mode="after")
    def validate_call_result_match(self) -> "ToolExecution":
        if self.call.call_id != self.result.call_id:
            raise ValueError(
                "Tool call and result must have the same call_id."
            )

        if self.call.tool_name != self.result.tool_name:
            raise ValueError(
                "Tool call and result must have the same tool_name."
            )

        return self


class ModelRequest(BaseModel):
    """Provider-neutral input passed from the agent to a model client."""

    user_message: str = Field(min_length=1)
    tool_executions: list[ToolExecution] = Field(
        default_factory=list
    )
    tools: list[ToolDefinition] = Field(
        default_factory=list
    )


class ToolCallResponse(BaseModel):
    """A model response requesting one tool execution."""

    type: Literal["tool_call"] = "tool_call"
    tool_call: ToolCall


class FinalAnswerResponse(BaseModel):
    """A model response indicating that the agent run can finish."""

    type: Literal["final_answer"] = "final_answer"
    answer: str = Field(min_length=1)


ModelResponse: TypeAlias = (
    ToolCallResponse
    | FinalAnswerResponse
)


class AgentResult(BaseModel):
    """The successful final result of one agent run."""

    answer: str = Field(min_length=1)
    tool_executions: list[ToolExecution] = Field(
        default_factory=list
    )
    steps: int = Field(ge=0)