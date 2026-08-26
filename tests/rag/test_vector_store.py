import pytest

from app.rag.contracts import JobDocument, VectorSearchResult
from app.rag.vector_store import InMemoryVectorStore


def make_document(document_id: int) -> JobDocument:
    return JobDocument(
        id=document_id,
        content=f"Job {document_id}",
        metadata={"job_id": document_id},
    )


def test_add_makes_document_searchable() -> None:
    store = InMemoryVectorStore()
    document = make_document(1)

    store.add(document, [1.0, 0.0])

    results = store.search([1.0, 0.0], top_k=1)

    assert results == [
        VectorSearchResult(document=document, score=1.0),
    ]


def test_search_orders_documents_by_cosine_similarity() -> None:
    store = InMemoryVectorStore()
    first = make_document(1)
    second = make_document(2)
    store.add(first, [1.0, 0.0])
    store.add(second, [0.0, 1.0])

    results = store.search([0.1, 1.0], top_k=2)

    assert [result.document for result in results] == [second, first]
    assert results[0].score == pytest.approx(1.0 / (1.01**0.5))
    assert results[1].score == pytest.approx(0.1 / (1.01**0.5))


def test_search_limits_results_to_top_k() -> None:
    store = InMemoryVectorStore()
    documents = [make_document(document_id) for document_id in range(1, 4)]
    store.add(documents[0], [1.0, 0.0])
    store.add(documents[1], [0.8, 0.2])
    store.add(documents[2], [0.0, 1.0])

    results = store.search([1.0, 0.0], top_k=2)

    assert [result.document for result in results] == documents[:2]
    assert all(isinstance(result.score, float) for result in results)


def test_search_empty_store_returns_empty_list() -> None:
    store = InMemoryVectorStore()

    assert store.search([1.0, 0.0], top_k=3) == []
