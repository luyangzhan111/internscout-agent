from datetime import date, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.rag.contracts import (
    JobDocument,
    RetrievalResult,
    VectorSearchResult,
)
from app.rag.embedding import EmbeddingProvider
from app.rag.retriever import JobKnowledgeRetriever
from app.rag.vector_store import InMemoryVectorStore, VectorStore
from app.schemas.job_response import JobRead


class RecordingEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self.batch_calls: list[list[str]] = []
        self.embed_calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.embed_calls.append(text)
        return self._vector_for(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.batch_calls.append(list(texts))
        return [self._vector_for(text) for text in texts]

    @staticmethod
    def _vector_for(text: str) -> list[float]:
        if text == "python query":
            return [1.0, 0.0]
        if "Relevant" in text:
            return [0.9, 0.1]
        return [0.0, 1.0]


class FixedResultVectorStore(VectorStore):
    """Return provider-defined scores to verify Retriever remains score-agnostic."""

    def __init__(self) -> None:
        self.documents: list[JobDocument] = []
        self.search_calls: list[tuple[list[float], int]] = []

    def add(self, document: JobDocument, embedding: list[float]) -> None:
        self.documents.append(document)

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
    ) -> list[VectorSearchResult]:
        self.search_calls.append((query_embedding, top_k))
        return [
            VectorSearchResult(document=self.documents[1], score=0.25),
            VectorSearchResult(document=self.documents[0], score=0.75),
        ][:top_k]


def make_job(job_id: int, title: str) -> JobRead:
    return JobRead(
        id=job_id,
        title=title,
        company="Example Tech",
        city="Shenzhen",
        salary=None,
        description="A searchable job description.",
        skills=["Python"],
        source="mock",
        source_url=f"https://example.com/jobs/{job_id}",
        published_at=date(2026, 8, 1),
        created_at=datetime(2026, 8, 1, 10, 0),
    )


def make_retriever(
    provider: RecordingEmbeddingProvider | None = None,
) -> tuple[JobKnowledgeRetriever, RecordingEmbeddingProvider]:
    provider = provider or RecordingEmbeddingProvider()
    return (
        JobKnowledgeRetriever(
            embedding_provider=provider,
            vector_store=InMemoryVectorStore(),
        ),
        provider,
    )


def test_retrieval_result_has_document_and_score_and_forbids_extras() -> None:
    document = JobDocument(
        id=1,
        content="Relevant job",
        metadata={"job_id": 1},
    )

    result = RetrievalResult(document=document, score=0.9)

    assert result.document == document
    assert result.score == 0.9
    with pytest.raises(ValidationError):
        RetrievalResult(document=document, score=0.9, extra="rejected")


def test_index_jobs_builds_documents_and_embeds_batch() -> None:
    retriever, provider = make_retriever()
    jobs = [make_job(1, "Relevant Python Intern"), make_job(2, "Other Intern")]

    retriever.index_jobs(jobs)

    assert len(provider.batch_calls) == 1
    assert len(provider.batch_calls[0]) == 2
    assert "Title: Relevant Python Intern" in provider.batch_calls[0][0]
    assert "Title: Other Intern" in provider.batch_calls[0][1]


def test_search_embeds_only_query_and_returns_cosine_ranking() -> None:
    retriever, provider = make_retriever()
    retriever.index_jobs([
        make_job(1, "Relevant Python Intern"),
        make_job(2, "Other Intern"),
    ])

    results = retriever.search("python query", top_k=2)

    assert provider.embed_calls == ["python query"]
    assert [result.document.id for result in results] == [1, 2]
    assert results[0].score == pytest.approx(0.9 / (0.9**2 + 0.1**2) ** 0.5)
    assert results[1].score == 0.0


def test_retriever_maps_vector_scores_without_recomputing_or_resorting() -> None:
    provider = RecordingEmbeddingProvider()
    store = FixedResultVectorStore()
    retriever = JobKnowledgeRetriever(
        embedding_provider=provider,
        vector_store=store,
    )
    retriever.index_jobs([
        make_job(1, "Relevant Python Intern"),
        make_job(2, "Other Intern"),
    ])

    results = retriever.search("python query", top_k=2)

    assert results == [
        RetrievalResult(document=store.documents[1], score=0.25),
        RetrievalResult(document=store.documents[0], score=0.75),
    ]
    assert store.search_calls == [([1.0, 0.0], 2)]


def test_search_top_k_and_larger_than_index_are_handled() -> None:
    retriever, _ = make_retriever()
    retriever.index_jobs([
        make_job(1, "Relevant Python Intern"),
        make_job(2, "Other Intern"),
    ])

    assert len(retriever.search("python query", top_k=1)) == 1
    assert len(retriever.search("python query", top_k=10)) == 2


def test_empty_jobs_and_empty_index_return_empty_without_embedding() -> None:
    retriever, provider = make_retriever()

    retriever.index_jobs([])

    assert retriever.search("python query", top_k=3) == []
    assert provider.batch_calls == []
    assert provider.embed_calls == []


@pytest.mark.parametrize("query", ["", "   ", "\t\n"])
def test_blank_query_is_rejected(query: str) -> None:
    retriever, _ = make_retriever()
    retriever.index_jobs([make_job(1, "Relevant Python Intern")])

    with pytest.raises(ValueError, match="query"):
        retriever.search(query, top_k=1)


@pytest.mark.parametrize("top_k", [0, -1])
def test_nonpositive_top_k_is_rejected(top_k: int) -> None:
    retriever, _ = make_retriever()

    with pytest.raises(ValueError, match="top_k"):
        retriever.search("python query", top_k=top_k)


@pytest.mark.parametrize("top_k", [True, 1.5, "1", None])
def test_noninteger_top_k_is_rejected(top_k: Any) -> None:
    retriever, _ = make_retriever()

    with pytest.raises(TypeError, match="top_k"):
        retriever.search("python query", top_k=top_k)


def test_repeated_search_has_deterministic_ranking() -> None:
    retriever, _ = make_retriever()
    retriever.index_jobs([
        make_job(1, "Relevant Python Intern"),
        make_job(2, "Other Intern"),
    ])

    first = retriever.search("python query", top_k=2)
    second = retriever.search("python query", top_k=2)

    assert [(item.document.id, item.score) for item in first] == [
        (item.document.id, item.score) for item in second
    ]
