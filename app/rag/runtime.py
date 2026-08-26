"""Application-level lifecycle management for job knowledge retrieval."""

from collections.abc import Callable
from threading import RLock

from app.rag.embedding import EmbeddingProvider
from app.rag.retriever import JobKnowledgeRetriever
from app.rag.vector_store import InMemoryVectorStore, VectorStore
from app.schemas.job_response import JobRead


class RetrievalRuntime:
    """Own the current job retriever and its rebuild lifecycle.

    The runtime only accepts an already-prepared job snapshot.  Each rebuild
    creates an independent vector store and retriever, then swaps the active
    retriever after indexing succeeds completely.
    """

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store_factory: Callable[[], VectorStore] = InMemoryVectorStore,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._vector_store_factory = vector_store_factory
        self._current_retriever: JobKnowledgeRetriever | None = None
        self._dirty = True
        self._lock = RLock()

    @property
    def current_retriever(self) -> JobKnowledgeRetriever | None:
        """Return the currently active retriever, if one has been built."""

        with self._lock:
            return self._current_retriever

    @property
    def is_dirty(self) -> bool:
        """Whether the active index needs to be rebuilt."""

        with self._lock:
            return self._dirty

    @property
    def is_ready(self) -> bool:
        """Whether a successfully built, current retriever is available."""

        with self._lock:
            return self._current_retriever is not None and not self._dirty

    def mark_dirty(self) -> None:
        """Mark the current index stale without changing or rebuilding it."""

        with self._lock:
            self._dirty = True

    def rebuild(self, jobs: list[JobRead]) -> None:
        """Build a fresh index from ``jobs`` and swap it in on success.

        The lifecycle lock covers construction and indexing so a concurrent
        ``mark_dirty`` cannot be overwritten by a completed rebuild.  The
        active retriever is never changed until all build steps succeed.
        """

        with self._lock:
            try:
                vector_store = self._vector_store_factory()
                new_retriever = JobKnowledgeRetriever(
                    embedding_provider=self._embedding_provider,
                    vector_store=vector_store,
                )
                new_retriever.index_jobs(jobs)
            except Exception:
                self._dirty = True
                raise

            self._current_retriever = new_retriever
            self._dirty = False
