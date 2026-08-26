import pytest

from app.rag.embedding import EmbeddingProvider, FakeEmbeddingProvider


def test_embedding_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        EmbeddingProvider()


def test_embed_returns_float_vector() -> None:
    provider = FakeEmbeddingProvider()

    embedding = provider.embed("Python backend internship")

    assert len(embedding) == provider.dimensions
    assert all(isinstance(value, float) for value in embedding)


def test_embed_batch_returns_one_vector_per_text() -> None:
    provider = FakeEmbeddingProvider()
    texts = ["Python internship", "Data internship"]

    embeddings = provider.embed_batch(texts)

    assert embeddings == [provider.embed(text) for text in texts]
    assert len(embeddings) == len(texts)


def test_fake_embedding_is_deterministic() -> None:
    first_provider = FakeEmbeddingProvider()
    second_provider = FakeEmbeddingProvider()

    assert first_provider.embed("same text") == second_provider.embed(
        "same text"
    )
