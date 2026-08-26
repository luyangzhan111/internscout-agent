"""Validated contracts for job knowledge documents."""

from pydantic import BaseModel, ConfigDict


class JobDocument(BaseModel):
    """A stable text representation of a job for downstream indexing."""

    model_config = ConfigDict(extra="forbid")

    id: int
    content: str
    metadata: dict[str, str | int]
