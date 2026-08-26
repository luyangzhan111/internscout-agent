"""Provider-neutral vector storage primitives."""

from abc import ABC, abstractmethod
from math import sqrt

from app.rag.contracts import JobDocument


class VectorStore(ABC):
    """Contract for storing and searching embedded job documents."""

    @abstractmethod
    def add(self, document: JobDocument, embedding: list[float]) -> None:
        """Store a document and its embedding."""

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int,
    ) -> list[JobDocument]:
        """Return the documents most similar to a query embedding."""


class InMemoryVectorStore(VectorStore):
    """Small in-memory store using cosine similarity for ranking."""

    def __init__(self) -> None:
        self._entries: list[tuple[JobDocument, tuple[float, ...]]] = []

    def add(self, document: JobDocument, embedding: list[float]) -> None:
        """Store independent snapshots of a document and its embedding."""

        self._entries.append(
            (document.model_copy(deep=True), tuple(embedding))
        )

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
    ) -> list[JobDocument]:
        """Rank stored documents by descending cosine similarity."""

        if top_k <= 0 or not self._entries:
            return []

        query = tuple(query_embedding)
        ranked: list[tuple[float, int, JobDocument]] = []
        for position, (document, embedding) in enumerate(self._entries):
            if len(embedding) != len(query):
                raise ValueError(
                    "query embedding dimension must match stored embeddings"
                )
            ranked.append(
                (
                    self._cosine_similarity(query, embedding),
                    position,
                    document,
                )
            )

        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [
            document.model_copy(deep=True)
            for _, _, document in ranked[:top_k]
        ]

    @staticmethod
    def _cosine_similarity(
        first: tuple[float, ...],
        second: tuple[float, ...],
    ) -> float:
        """Return cosine similarity, treating zero vectors as unrelated."""

        first_norm = sqrt(sum(value * value for value in first))
        second_norm = sqrt(sum(value * value for value in second))
        if first_norm == 0.0 or second_norm == 0.0:
            return 0.0
        dot_product = sum(
            first_value * second_value
            for first_value, second_value in zip(first, second)
        )
        return dot_product / (first_norm * second_norm)
