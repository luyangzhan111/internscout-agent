import json
from typing import Any

import pytest

from app.agent.contracts import ToolCall, ToolResult
from app.agent.tools.retrieval_tool import (
    RetrieveJobKnowledgeArguments,
    RetrieveJobKnowledgeTool,
)
from app.rag.contracts import JobDocument, RetrievalResult
from app.rag.retriever import JobKnowledgeRetriever


class RecordingRetriever(JobKnowledgeRetriever):
    def __init__(
        self,
        *,
        results: list[RetrievalResult] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.results = results or []
        self.error = error
        self.calls: list[tuple[str, int]] = []

    def search(
        self,
        query: str,
        top_k: int,
    ) -> list[RetrievalResult]:
        self.calls.append((query, top_k))
        if self.error is not None:
            raise self.error
        return self.results


def execute(
    tool: RetrieveJobKnowledgeTool,
    arguments: dict[str, Any] | None = None,
) -> ToolResult:
    return tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="retrieve_job_knowledge",
            arguments=arguments or {},
        )
    )


def make_result() -> RetrievalResult:
    return RetrievalResult(
        document=JobDocument(
            id=7,
            content="Title: Agent workflow internship",
            metadata={
                "job_id": 7,
                "company": "Example Tech",
            },
        ),
        score=0.875,
    )


def test_retrieval_tool_definition_uses_argument_schema() -> None:
    tool = RetrieveJobKnowledgeTool(RecordingRetriever())

    definition = tool.definition()

    assert definition.name == "retrieve_job_knowledge"
    assert definition.description == (
        "Retrieve relevant job knowledge from indexed job documents "
        "using a natural-language query."
    )
    assert definition.parameters == (
        RetrieveJobKnowledgeArguments.model_json_schema()
    )
    assert definition.parameters["required"] == ["query"]
    assert definition.parameters["additionalProperties"] is False
    assert definition.parameters["properties"]["top_k"]["default"] == 5
    assert definition.parameters["properties"]["top_k"]["maximum"] == 20


def test_retrieval_tool_normalizes_query_and_delegates_top_k() -> None:
    retriever = RecordingRetriever(results=[make_result()])
    tool = RetrieveJobKnowledgeTool(retriever)

    result = execute(
        tool,
        {
            "query": "  agent workflow  ",
            "top_k": 3,
        },
    )

    assert result.success is True
    assert retriever.calls == [("agent workflow", 3)]


def test_retrieval_tool_serializes_retrieval_results() -> None:
    result = execute(
        RetrieveJobKnowledgeTool(
            RecordingRetriever(results=[make_result()])
        ),
        {"query": "agent workflow"},
    )

    assert result.success is True
    assert result.data == [make_result().model_dump(mode="json")]
    json.dumps(result.data, ensure_ascii=False)


def test_retrieval_tool_returns_empty_result() -> None:
    result = execute(
        RetrieveJobKnowledgeTool(RecordingRetriever()),
        {"query": "agent workflow"},
    )

    assert result.success is True
    assert result.data == []


@pytest.mark.parametrize("query", ["", "   ", "\t\n"])
def test_retrieval_tool_rejects_blank_query(query: str) -> None:
    retriever = RecordingRetriever()

    result = execute(
        RetrieveJobKnowledgeTool(retriever),
        {"query": query},
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.startswith("Invalid tool arguments:")
    assert retriever.calls == []


@pytest.mark.parametrize("top_k", [0, -1, 21, 100])
def test_retrieval_tool_rejects_out_of_range_top_k(top_k: int) -> None:
    retriever = RecordingRetriever()

    result = execute(
        RetrieveJobKnowledgeTool(retriever),
        {"query": "agent workflow", "top_k": top_k},
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.startswith("Invalid tool arguments:")
    assert retriever.calls == []


@pytest.mark.parametrize("top_k", [True, 1.5, "5", None])
def test_retrieval_tool_rejects_noninteger_top_k(top_k: Any) -> None:
    retriever = RecordingRetriever()

    result = execute(
        RetrieveJobKnowledgeTool(retriever),
        {"query": "agent workflow", "top_k": top_k},
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.startswith("Invalid tool arguments:")
    assert retriever.calls == []


def test_retrieval_tool_rejects_unknown_argument() -> None:
    retriever = RecordingRetriever()

    result = execute(
        RetrieveJobKnowledgeTool(retriever),
        {"query": "agent workflow", "unexpected": True},
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.startswith("Invalid tool arguments:")
    assert retriever.calls == []


def test_retrieval_tool_converts_retriever_exception() -> None:
    tool = RetrieveJobKnowledgeTool(
        RecordingRetriever(error=RuntimeError("retrieval failed"))
    )

    result = execute(tool, {"query": "agent workflow"})

    assert result.success is False
    assert result.error == "Tool execution failed."
    assert "retrieval failed" not in result.error
