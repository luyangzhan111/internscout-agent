"""Validated contracts for job knowledge documents."""

from pydantic import BaseModel, ConfigDict


class JobDocument(BaseModel):
    """A stable text representation of a job for downstream indexing."""

    model_config = ConfigDict(extra="forbid")

    id: int
    content: str
    metadata: dict[str, str | int]


class VectorSearchResult(BaseModel):
    """A vector-store hit together with its similarity score."""

    model_config = ConfigDict(extra="forbid")

    document: JobDocument
    score: float


class RetrievalResult(BaseModel):
    """A retrieved document together with its similarity score."""

    model_config = ConfigDict(extra="forbid")

    document: JobDocument
    score: float
