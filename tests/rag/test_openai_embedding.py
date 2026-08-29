from types import SimpleNamespace
from typing import Any

import pytest

from app.rag.embedding import OpenAICompatibleEmbeddingProvider


class FakeEmbeddings:
    def __init__(
        self,
        *,
        responses: list[Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.responses = responses or []
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.responses.pop(0)


class FakeClient:
    def __init__(
        self,
        *,
        responses: list[Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.embeddings = FakeEmbeddings(responses=responses, error=error)


def embedding_response(*vectors: list[float]) -> Any:
    return SimpleNamespace(
        data=[
            SimpleNamespace(index=index, embedding=vector)
            for index, vector in enumerate(vectors)
        ]
    )


def provider(fake: FakeClient) -> OpenAICompatibleEmbeddingProvider:
    return OpenAICompatibleEmbeddingProvider(
        api_key="test-key",
        base_url="https://embedding.test/v1",
        model="test-embedding-model",
        dimensions=3,
        client=fake,
    )


def test_constructor_keeps_explicit_configuration() -> None:
    configured = provider(FakeClient())

    assert configured.model == "test-embedding-model"
    assert configured.dimensions == 3


def test_constructor_reads_dedicated_environment_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INTERNSCOUT_EMBEDDING_MODEL", "env-model")
    monkeypatch.setenv("INTERNSCOUT_EMBEDDING_DIMENSIONS", "4")
    monkeypatch.setenv("INTERNSCOUT_EMBEDDING_API_KEY", "env-key")
    monkeypatch.setenv(
        "INTERNSCOUT_EMBEDDING_BASE_URL",
        "https://env.embedding.test/v1",
    )

    captured: dict[str, Any] = {}

    class CapturingOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    import app.rag.embedding as embedding_module

    monkeypatch.setattr(embedding_module, "OpenAI", CapturingOpenAI)
    configured = OpenAICompatibleEmbeddingProvider()

    assert configured.model == "env-model"
    assert configured.dimensions == 4
    assert captured == {
        "api_key": "env-key",
        "base_url": "https://env.embedding.test/v1",
    }


def test_constructor_requires_key_and_endpoint_without_injected_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INTERNSCOUT_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("INTERNSCOUT_EMBEDDING_BASE_URL", raising=False)

    with pytest.raises(ValueError, match="INTERNSCOUT_EMBEDDING_API_KEY"):
        OpenAICompatibleEmbeddingProvider()


def test_embed_calls_api_and_converts_values_to_float() -> None:
    fake = FakeClient(responses=[embedding_response([1, 2.5, 3])])
    result = provider(fake).embed("岗位文本")

    assert result == [1.0, 2.5, 3.0]
    assert fake.embeddings.calls == [
        {
            "input": "岗位文本",
            "model": "test-embedding-model",
            "dimensions": 3,
        }
    ]


def test_embed_batch_empty_returns_without_api_call() -> None:
    fake = FakeClient()

    assert provider(fake).embed_batch([]) == []
    assert fake.embeddings.calls == []


def test_embed_batch_up_to_ten_texts_uses_one_request() -> None:
    texts = [f"text-{index}" for index in range(10)]
    fake = FakeClient(
        responses=[embedding_response(*([1.0, 2.0, 3.0] for _ in texts))]
    )

    result = provider(fake).embed_batch(texts)

    assert len(result) == 10
    assert len(fake.embeddings.calls) == 1
    assert fake.embeddings.calls[0]["input"] == texts


def test_embed_batch_splits_twenty_three_texts_and_preserves_order() -> None:
    texts = [f"text-{index}" for index in range(23)]
    responses: list[Any] = []
    for start, size in ((0, 10), (10, 10), (20, 3)):
        responses.append(
            embedding_response(
                *([float(index), 0.0, 1.0] for index in range(start, start + size))
            )
        )
    fake = FakeClient(responses=responses)

    result = provider(fake).embed_batch(texts)

    assert len(result) == 23
    assert [call["input"] for call in fake.embeddings.calls] == [
        texts[:10],
        texts[10:20],
        texts[20:],
    ]
    assert [vector[0] for vector in result] == [float(index) for index in range(23)]


def test_out_of_order_response_indexes_are_reordered() -> None:
    fake = FakeClient(
        responses=[
            SimpleNamespace(
                data=[
                    SimpleNamespace(index=1, embedding=[2.0, 0.0, 1.0]),
                    SimpleNamespace(index=0, embedding=[1.0, 0.0, 1.0]),
                ]
            )
        ]
    )

    assert provider(fake).embed_batch(["first", "second"]) == [
        [1.0, 0.0, 1.0],
        [2.0, 0.0, 1.0],
    ]


def test_rejects_response_count_mismatch() -> None:
    fake = FakeClient(responses=[embedding_response([1.0, 2.0, 3.0])])

    with pytest.raises(ValueError, match="count"):
        provider(fake).embed_batch(["one", "two"])


def test_rejects_response_dimension_mismatch() -> None:
    fake = FakeClient(responses=[embedding_response([1.0, 2.0])])

    with pytest.raises(ValueError, match="dimension"):
        provider(fake).embed("one")


def test_api_exception_is_sanitized() -> None:
    fake = FakeClient(error=RuntimeError("request failed with secret-key"))

    with pytest.raises(RuntimeError, match="embedding API request failed") as error:
        provider(fake).embed("one")

    assert "secret-key" not in str(error.value)


@pytest.mark.parametrize(
    ("method", "value", "error", "message"),
    [
        ("embed", "   ", ValueError, "blank"),
        ("embed", 123, TypeError, "string"),
        ("embed_batch", ["ok", "  "], ValueError, "blank"),
        ("embed_batch", ("ok",), TypeError, "list"),
    ],
)
def test_input_validation(
    method: str,
    value: Any,
    error: type[Exception],
    message: str,
) -> None:
    fake = FakeClient()

    with pytest.raises(error, match=message):
        getattr(provider(fake), method)(value)
