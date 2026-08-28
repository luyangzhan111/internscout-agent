"""Contracts for the offline direct retrieval evaluation dataset."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from evals.contracts import CaseScore


_CASE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class RetrievalEvalCase(BaseModel):
    """One versioned, provider-neutral direct retrieval case."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    case_id: str = Field(
        min_length=1,
        pattern=_CASE_ID_PATTERN.pattern,
    )
    description: str = Field(min_length=1)
    query: str = Field(min_length=1)
    top_k: int = Field(strict=True, gt=0, le=20)
    expected_job_id: int = Field(strict=True, gt=0)

    @field_validator("schema_version", mode="before")
    @classmethod
    def reject_boolean_schema_version(cls, value: object) -> object:
        """Keep JSON Schema integer semantics for the version literal."""

        if isinstance(value, bool):
            raise ValueError("schema_version must be integer 1, not boolean")
        return value

    @field_validator("case_id", "description", "query")
    @classmethod
    def validate_meaningful_text(cls, value: str) -> str:
        """Reject strings that contain no meaningful non-whitespace text."""

        if not value.strip():
            raise ValueError("value must contain non-whitespace text")
        return value


class RetrievalEvaluationCaseResult(BaseModel):
    """Execution result for one direct retrieval evaluation case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    status: Literal["completed", "failed"]
    retrieved_job_ids: list[int] = Field(default_factory=list)
    error_type: str | None = None
    error_message: str | None = None


class RetrievalEvaluationRunResult(BaseModel):
    """Structured execution results for a direct retrieval evaluation run."""

    model_config = ConfigDict(extra="forbid")

    case_results: list[RetrievalEvaluationCaseResult]
    completed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)

    @property
    def results(self) -> list[RetrievalEvaluationCaseResult]:
        """Expose the case results using the Stage 12-style terminology."""

        return self.case_results


class RetrievalEvaluationScore(BaseModel):
    """Aggregated ID-and-order score for one retrieval evaluation run."""

    model_config = ConfigDict(extra="forbid")

    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    case_pass_rate: float = Field(ge=0, le=1)
    hit_at_k_rate: float = Field(ge=0, le=1)
    top_1_hit_rate: float = Field(ge=0, le=1)
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
