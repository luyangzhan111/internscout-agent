"""Agent HTTP API request and response models."""

from pydantic import BaseModel, ConfigDict, Field

from app.matching.contracts import JobMatchResult


class AgentQueryRequest(BaseModel):
    """One independent user query for the agent."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    user_message: str = Field(
        min_length=1,
        description="User request for the agent to answer.",
    )
    include_recommendations: bool = Field(
        default=False,
        description=(
            "Whether to include structured match_jobs results."
        ),
    )


class AgentQueryResponse(BaseModel):
    """Public result of a completed agent query."""

    answer: str = Field(
        min_length=1,
        description="Agent final answer.",
    )
    steps: int = Field(
        ge=0,
        description="Number of model decisions made.",
    )
    tool_execution_count: int = Field(
        ge=0,
        description="Number of tools executed.",
    )
    recommendations: list[JobMatchResult] | None = Field(
        default=None,
        description=(
            "Structured recommendations from a successful match_jobs "
            "tool execution."
        ),
    )
