from datetime import date, datetime

import pytest

from app.rag.embedding import EmbeddingProvider, FakeEmbeddingProvider
from app.rag.retriever import JobKnowledgeRetriever
from app.rag.runtime import RetrievalRuntime
from app.rag.vector_store import InMemoryVectorStore, VectorStore
from app.schemas.job_response import JobRead


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


class FailingEmbeddingProvider(EmbeddingProvider):
    def embed(self, text: str) -> list[float]:
        raise RuntimeError("embedding failed")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding failed")


class FailingVectorStore(VectorStore):
    def add(self, document, embedding) -> None:
        raise RuntimeError("store add failed")

    def search(self, query_embedding, top_k):
        return []


def test_initial_state_is_dirty_and_has_no_retriever() -> None:
    runtime = RetrievalRuntime(
        embedding_provider=FakeEmbeddingProvider(),
    )

    assert runtime.current_retriever is None
    assert runtime.is_dirty is True
    assert runtime.is_ready is False


def test_successful_rebuild_creates_searchable_retriever() -> None:
    runtime = RetrievalRuntime(
        embedding_provider=FakeEmbeddingProvider(),
    )

    runtime.rebuild([make_job(1, "Python Intern")])

    assert isinstance(runtime.current_retriever, JobKnowledgeRetriever)
    assert runtime.is_dirty is False
    assert runtime.is_ready is True
    assert [result.document.id for result in runtime.current_retriever.search(
        "python", top_k=5
    )] == [1]


def test_mark_dirty_keeps_old_retriever_without_rebuilding() -> None:
    provider = FakeEmbeddingProvider()
    runtime = RetrievalRuntime(embedding_provider=provider)
    runtime.rebuild([make_job(1, "Python Intern")])
    old_retriever = runtime.current_retriever

    runtime.mark_dirty()

    assert runtime.current_retriever is old_retriever
    assert runtime.is_dirty is True
    assert runtime.is_ready is False
    assert [result.document.id for result in old_retriever.search(
        "python", top_k=5
    )] == [1]


def test_second_rebuild_replaces_first_index() -> None:
    runtime = RetrievalRuntime(embedding_provider=FakeEmbeddingProvider())
    runtime.rebuild([make_job(1, "First Intern"), make_job(2, "Second Intern")])

    runtime.rebuild([make_job(3, "Replacement Intern")])

    assert [result.document.id for result in runtime.current_retriever.search(
        "intern", top_k=10
    )] == [3]


def test_rebuild_empty_snapshot_replaces_old_index_with_empty_index() -> None:
    runtime = RetrievalRuntime(embedding_provider=FakeEmbeddingProvider())
    runtime.rebuild([make_job(1, "Existing Intern")])

    runtime.rebuild([])

    assert runtime.current_retriever is not None
    assert runtime.is_dirty is False
    assert runtime.current_retriever.search("intern", top_k=10) == []


def test_failed_first_rebuild_leaves_runtime_unready_and_dirty() -> None:
    runtime = RetrievalRuntime(
        embedding_provider=FailingEmbeddingProvider(),
    )

    with pytest.raises(RuntimeError, match="embedding failed"):
        runtime.rebuild([make_job(1, "Failed Intern")])

    assert runtime.current_retriever is None
    assert runtime.is_dirty is True
    assert runtime.is_ready is False


def test_failed_rebuild_preserves_old_retriever_and_index() -> None:
    stores = [InMemoryVectorStore(), FailingVectorStore()]
    created_stores: list[VectorStore] = []

    def factory() -> VectorStore:
        store = stores.pop(0)
        created_stores.append(store)
        return store

    provider = FakeEmbeddingProvider()
    runtime = RetrievalRuntime(
        embedding_provider=provider,
        vector_store_factory=factory,
    )
    runtime.rebuild([make_job(1, "Stable Intern")])
    old_retriever = runtime.current_retriever

    with pytest.raises(RuntimeError, match="store add failed"):
        runtime.rebuild([make_job(2, "Broken Intern")])

    assert len(created_stores) == 2
    assert runtime.current_retriever is old_retriever
    assert runtime.is_dirty is True
    assert [result.document.id for result in old_retriever.search(
        "intern", top_k=10
    )] == [1]


def test_rebuild_uses_a_fresh_vector_store_each_time() -> None:
    stores: list[InMemoryVectorStore] = []

    def factory() -> VectorStore:
        store = InMemoryVectorStore()
        stores.append(store)
        return store

    runtime = RetrievalRuntime(
        embedding_provider=FakeEmbeddingProvider(),
        vector_store_factory=factory,
    )
    runtime.rebuild([make_job(1, "First Intern")])
    first_store = stores[0]

    runtime.rebuild([make_job(2, "Second Intern")])

    assert len(stores) == 2
    assert stores[1] is not first_store
    assert [result.document.id for result in runtime.current_retriever.search(
        "intern", top_k=10
    )] == [2]


def test_runtime_rebuilds_only_from_prepared_jobs() -> None:
    runtime = RetrievalRuntime(embedding_provider=FakeEmbeddingProvider())

    runtime.rebuild([make_job(1, "Prepared Intern")])

    assert runtime.current_retriever is not None
    assert runtime.current_retriever.search("prepared", top_k=1)
