"""Provider-neutral text embedding primitives."""

from abc import ABC, abstractmethod
from hashlib import sha256
import os
from typing import Any

from openai import OpenAI


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


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """Embedding provider for OpenAI-compatible embedding APIs.

    The default model and dimensions target Alibaba Cloud Bailian's
    ``text-embedding-v4`` model.  The endpoint and credentials are supplied
    explicitly or read from the dedicated environment variables when a real
    SDK client is constructed.  A client can be injected for deterministic,
    network-free tests.
    """

    _MAX_BATCH_SIZE = 10
    _DEFAULT_MODEL = "text-embedding-v4"
    _DEFAULT_DIMENSIONS = 1024

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = self._resolve_text_config(
            model,
            env_name="INTERNSCOUT_EMBEDDING_MODEL",
            default=self._DEFAULT_MODEL,
        )
        self.dimensions = self._resolve_dimensions(dimensions)

        if api_key is not None and (
            not isinstance(api_key, str) or not api_key.strip()
        ):
            raise ValueError("api_key cannot be blank.")
        if base_url is not None and (
            not isinstance(base_url, str) or not base_url.strip()
        ):
            raise ValueError("base_url cannot be blank.")

        resolved_api_key = (
            api_key
            if api_key is not None
            else os.getenv("INTERNSCOUT_EMBEDDING_API_KEY")
        )
        resolved_base_url = (
            base_url
            if base_url is not None
            else os.getenv("INTERNSCOUT_EMBEDDING_BASE_URL")
        )

        if client is None:
            if not isinstance(resolved_api_key, str) or not resolved_api_key.strip():
                raise ValueError(
                    "INTERNSCOUT_EMBEDDING_API_KEY is required when no client is injected."
                )
            if not isinstance(resolved_base_url, str) or not resolved_base_url.strip():
                raise ValueError(
                    "INTERNSCOUT_EMBEDDING_BASE_URL is required when no client is injected."
                )
            client = OpenAI(
                api_key=resolved_api_key,
                base_url=resolved_base_url,
            )

        self._client = client

    def embed(self, text: str) -> list[float]:
        """Embed one non-blank text value and return plain Python floats."""

        self._validate_text(text)
        vectors = self._request_embeddings(text, expected_count=1)
        return vectors[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed texts in transparent batches while preserving input order."""

        if not isinstance(texts, list):
            raise TypeError("texts must be a list of strings.")
        for text in texts:
            self._validate_text(text)

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._MAX_BATCH_SIZE):
            batch = texts[start : start + self._MAX_BATCH_SIZE]
            vectors.extend(
                self._request_embeddings(batch, expected_count=len(batch))
            )
        return vectors

    def _request_embeddings(
        self,
        input_value: str | list[str],
        *,
        expected_count: int,
    ) -> list[list[float]]:
        try:
            response = self._client.embeddings.create(
                input=input_value,
                model=self.model,
                dimensions=self.dimensions,
            )
        except Exception:
            # Do not expose SDK exceptions because they can include request
            # details or provider configuration.
            raise RuntimeError("embedding API request failed.") from None

        data = self._field(response, "data")
        if not isinstance(data, list):
            raise ValueError("embedding API response data must be a list.")
        if len(data) != expected_count:
            raise ValueError(
                "embedding API response count does not match the request."
            )

        ordered_data = self._order_response_data(data)
        vectors: list[list[float]] = []
        for item in ordered_data:
            raw_embedding = self._field(item, "embedding")
            if not isinstance(raw_embedding, (list, tuple)):
                raise ValueError(
                    "embedding API response contains an invalid vector."
                )
            if len(raw_embedding) != self.dimensions:
                raise ValueError(
                    "embedding API response vector dimension does not match "
                    "the configured dimensions."
                )

            vector: list[float] = []
            for value in raw_embedding:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(
                        "embedding API response vector contains a non-numeric value."
                    )
                vector.append(float(value))
            vectors.append(vector)
        return vectors

    @classmethod
    def _order_response_data(cls, data: list[Any]) -> list[Any]:
        indices = [cls._field(item, "index") for item in data]
        if all(isinstance(index, int) and not isinstance(index, bool) for index in indices):
            if sorted(indices) != list(range(len(data))):
                raise ValueError("embedding API response indexes are invalid.")
            return [item for _, item in sorted(zip(indices, data), key=lambda pair: pair[0])]
        if any(index is not None for index in indices):
            raise ValueError("embedding API response indexes are invalid.")
        return data

    @staticmethod
    def _field(value: Any, name: str) -> Any:
        if isinstance(value, dict):
            return value.get(name)
        return getattr(value, name, None)

    @staticmethod
    def _validate_text(text: str) -> None:
        if not isinstance(text, str):
            raise TypeError("text must be a string.")
        if not text.strip():
            raise ValueError("text cannot be blank.")

    @staticmethod
    def _resolve_text_config(
        value: str | None,
        *,
        env_name: str,
        default: str,
    ) -> str:
        resolved = value if value is not None else os.getenv(env_name, default)
        if not isinstance(resolved, str) or not resolved.strip():
            raise ValueError(f"{env_name} cannot be blank.")
        return resolved.strip()

    @classmethod
    def _resolve_dimensions(cls, value: int | None) -> int:
        if value is None:
            raw_value = os.getenv(
                "INTERNSCOUT_EMBEDDING_DIMENSIONS",
                str(cls._DEFAULT_DIMENSIONS),
            )
            try:
                value = int(raw_value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "INTERNSCOUT_EMBEDDING_DIMENSIONS must be an integer."
                ) from exc
        if type(value) is not int or value <= 0:
            raise ValueError("dimensions must be greater than zero.")
        return value
