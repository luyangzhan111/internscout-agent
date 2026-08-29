"""Agent Tool adapter for indexed job knowledge retrieval."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agent.tools.base import BaseTool
from app.rag.retriever import JobKnowledgeRetriever


class RetrieveJobKnowledgeArguments(BaseModel):
    """Validated arguments accepted by the retrieval tool."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    top_k: int = Field(
        default=5,
        strict=True,
        ge=1,
        le=20,
    )

    @field_validator("query", mode="before")
    @classmethod
    def normalize_query(cls, value: Any) -> Any:
        """Trim the query and reject blank text."""

        if not isinstance(value, str):
            return value

        normalized = value.strip()
        if not normalized:
            raise ValueError("query cannot be blank.")

        return normalized


class RetrieveJobKnowledgeTool(
    BaseTool[RetrieveJobKnowledgeArguments]
):
    """Read-only adapter exposing indexed job knowledge to the Agent."""

    name = "retrieve_job_knowledge"
    description = (
        "Retrieve relevant job knowledge from indexed job documents "
        "using a natural-language query."
    )
    args_schema = RetrieveJobKnowledgeArguments

    def __init__(
        self,
        retriever: JobKnowledgeRetriever,
    ) -> None:
        self._retriever = retriever

    def _run(
        self,
        arguments: RetrieveJobKnowledgeArguments,
    ) -> list[dict[str, Any]]:
        results = self._retriever.search(
            query=arguments.query,
            top_k=arguments.top_k,
        )

        return [
            result.model_dump(mode="json")
            for result in results
        ]
