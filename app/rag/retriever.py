"""Semantic retrieval orchestration for indexed job documents."""

from app.rag.contracts import RetrievalResult
from app.rag.document import build_job_document
from app.rag.embedding import EmbeddingProvider
from app.rag.vector_store import VectorStore
from app.schemas.job_response import JobRead


class JobKnowledgeRetriever:
    """Build a job index once, then embed and search individual queries."""

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store
        self._has_index = False

    def index_jobs(self, jobs: list[JobRead]) -> None:
        """Transform, embed, and add jobs to the configured vector store."""

        documents = [build_job_document(job) for job in jobs]
        if not documents:
            self._has_index = False
            return

        embeddings = self._embedding_provider.embed_batch(
            [document.content for document in documents]
        )
        if len(embeddings) != len(documents):
            raise ValueError(
                "embedding provider must return one vector per document"
            )

        for document, embedding in zip(documents, embeddings):
            self._vector_store.add(document, embedding)
        self._has_index = True

    def search(
        self,
        query: str,
        top_k: int,
    ) -> list[RetrievalResult]:
        """Embed a query and return ranked results from the current index."""

        self._validate_query(query)
        self._validate_top_k(top_k)

        if not self._has_index:
            return []

        query_embedding = self._embedding_provider.embed(query)
        vector_results = self._vector_store.search(
            query_embedding,
            top_k,
        )
        return [
            RetrievalResult(
                document=result.document,
                score=result.score,
            )
            for result in vector_results
        ]

    @staticmethod
    def _validate_query(query: str) -> None:
        if not isinstance(query, str):
            raise TypeError("query must be a string.")
        if not query.strip():
            raise ValueError("query cannot be blank.")

    @staticmethod
    def _validate_top_k(top_k: int) -> None:
        if type(top_k) is not int:
            raise TypeError("top_k must be an integer.")
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")
