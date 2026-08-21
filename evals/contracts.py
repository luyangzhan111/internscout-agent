"""Contracts for the offline Agent Evaluation dataset and runs."""

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agent.contracts import AgentResult


_DATA_ASSERTION_PATH_PATTERN = re.compile(
    r"^(?:\$|[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*|"
    r"items\[0\](?:\.[A-Za-z_][A-Za-z0-9_]*)*)$"
)


class EvalToolCall(BaseModel):
    """Expected model-issued Tool call metadata for one evaluation case."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class EvalDataAssertion(BaseModel):
    """One deterministic assertion against a ToolResult.data value.

    Supported paths are object fields, nested object fields, ``items[0]``
    paths, and ``$`` for the root value.  ``items[0]`` also addresses the
    first item when the ToolResult.data value itself is a list.
    """

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    equals: Any = None
    contains: Any = None

    @model_validator(mode="after")
    def validate_assertion(self) -> "EvalDataAssertion":
        if not _DATA_ASSERTION_PATH_PATTERN.fullmatch(self.path):
            raise ValueError(
                "data assertion path must use '$', object fields, "
                "or items[0] paths."
            )

        has_equals = "equals" in self.model_fields_set
        has_contains = "contains" in self.model_fields_set
        if has_equals == has_contains:
            raise ValueError(
                "data assertion must define exactly one of "
                "'equals' or 'contains'."
            )
        return self


class EvalToolResult(BaseModel):
    """Expected observable result metadata for one Tool execution."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1)
    success: bool
    error_contains: list[str] = Field(default_factory=list)
    data_assertions: list[EvalDataAssertion] = Field(default_factory=list)


class EvalAnswerAssertions(BaseModel):
    """Stable answer assertions reserved for a future scorer."""

    model_config = ConfigDict(extra="forbid")

    contains: list[str]
    excludes: list[str]


class EvalExpectation(BaseModel):
    """Expected execution shape for one evaluation case."""

    model_config = ConfigDict(extra="forbid")

    outcome: Literal["success", "controlled_failure"]
    tool_sequence: list[str]
    tool_calls: list[EvalToolCall]
    tool_results: list[EvalToolResult]
    answer: EvalAnswerAssertions


class EvalCase(BaseModel):
    """One versioned, provider-neutral evaluation case."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    case_id: str = Field(min_length=1)
    category: Literal[
        "search_jobs",
        "get_job_detail",
        "match_jobs",
        "failure",
    ]
    description: str = Field(min_length=1)
    user_message: str = Field(min_length=1)
    expected: EvalExpectation


class EvaluationCaseResult(BaseModel):
    """Execution result for one case; no scoring is performed here."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    status: Literal["completed", "failed"]
    agent_result: AgentResult | None = None
    error_type: str | None = None
    error_message: str | None = None


class EvaluationRunResult(BaseModel):
    """Structured result for one offline dataset execution."""

    model_config = ConfigDict(extra="forbid")

    dataset_path: str = Field(min_length=1)
    results: list[EvaluationCaseResult]
    total_cases: int = Field(ge=0)
    completed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)


class MetricResult(BaseModel):
    """Explainable result for one deterministic evaluation metric."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    passed: bool
    expected: Any
    actual: Any
    reason: str = Field(min_length=1)


class CaseScore(BaseModel):
    """Score for one case, including every core metric observation."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL"]
    metrics: list[MetricResult]
    failure_reasons: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return the boolean form of the public PASS/FAIL status."""

        return self.status == "PASS"


class EvaluationScore(BaseModel):
    """Aggregated deterministic scores for one evaluation run."""

    model_config = ConfigDict(extra="forbid")

    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    case_pass_rate: float = Field(ge=0, le=1)
    metric_pass_rates: dict[str, float] = Field(default_factory=dict)
    failed_case_ids: list[str] = Field(default_factory=list)
    case_scores: list[CaseScore] = Field(default_factory=list)
    missing_case_ids: list[str] = Field(default_factory=list)
    unexpected_case_ids: list[str] = Field(default_factory=list)
    alignment_errors: list[str] = Field(default_factory=list)
    status: Literal["PASS", "FAIL"]

    @property
    def passed(self) -> bool:
        """Return whether the run is fully passable for CI purposes."""

        return self.status == "PASS"
