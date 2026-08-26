"""Provider-neutral text embedding primitives."""

from abc import ABC, abstractmethod
from hashlib import sha256


class EmbeddingProvider(ABC):
    """Contract for converting text into embedding vectors."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return an embedding vector for one text value."""

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector for each text value."""


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic, network-free embedding provider for tests."""

    def __init__(self, dimensions: int = 8) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be greater than zero")
        if dimensions > sha256().digest_size:
            raise ValueError("dimensions cannot exceed 32")
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        """Map a UTF-8 string to stable values in the range [0, 1]."""

        digest = sha256(text.encode("utf-8")).digest()
        return [value / 255.0 for value in digest[: self.dimensions]]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed texts in input order."""

        return [self.embed(text) for text in texts]
