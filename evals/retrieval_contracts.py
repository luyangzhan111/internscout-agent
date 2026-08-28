"""Contracts for the offline direct retrieval evaluation dataset."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
