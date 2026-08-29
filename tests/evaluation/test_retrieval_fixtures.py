"""Tests for the controlled semantic retrieval fixture."""

import inspect

import pytest

from app.rag.document import build_job_document
from app.rag.retriever import JobKnowledgeRetriever
from evals.retrieval_dataset import load_retrieval_cases
from tests.evaluation.retrieval_fixtures import (
    ControlledEmbeddingProvider,
    build_controlled_retriever,
    build_evaluation_jobs,
)


def test_controlled_embedding_is_deterministic() -> None:
    text = "大模型 Agent RAG 工具调用实习岗位"
    first = ControlledEmbeddingProvider()
    second = ControlledEmbeddingProvider()

    assert first.embed(text) == first.embed(text)
    assert first.embed(text) == second.embed(text)


def test_controlled_embedding_has_fixed_float_dimensions() -> None:
    provider = ControlledEmbeddingProvider()

    embeddings = provider.embed_batch(
        [
            "Python FastAPI 后端接口 数据库",
            "Linux Docker CI 部署",
            "没有受控概念的文本",
        ]
    )

    assert provider.dimensions == 6
    assert all(len(embedding) == provider.dimensions for embedding in embeddings)
    assert all(
        isinstance(value, float)
        for embedding in embeddings
        for value in embedding
    )


def test_embed_batch_preserves_input_order() -> None:
    provider = ControlledEmbeddingProvider()
    texts = [
        "Linux Docker CI 部署",
        "网页采集 HTML解析 数据清洗",
        "Pytest 接口自动化测试",
    ]

    assert provider.embed_batch(texts) == [provider.embed(text) for text in texts]


def test_ci_alias_uses_word_boundaries_and_preserves_devops_evidence() -> None:
    provider = ControlledEmbeddingProvider()
    devops_axis = provider.CONCEPT_AXES.index("devops")

    assert provider.embed("CI")[devops_axis] > 0.0
    assert provider.embed("CI pipeline")[devops_axis] > 0.0
    assert provider.embed("Docker CI deployment")[devops_axis] > 0.0
    assert provider.embed("CI/CD")[devops_axis] > 0.0

    for text in ("City:", "City: Shenzhen", "specific", "citation"):
        assert provider.embed(text)[devops_axis] == 0.0


def test_ascii_aliases_match_tokens_without_breaking_fastapi_evidence() -> None:
    provider = ControlledEmbeddingProvider()
    backend_axis = provider.CONCEPT_AXES.index("backend_api")
    ai_axis = provider.CONCEPT_AXES.index("ai_rag_agent")
    data_axis = provider.CONCEPT_AXES.index("data_crawling")

    assert provider.embed("API")[backend_axis] > 0.0
    assert provider.embed("FastAPI")[backend_axis] > 0.0
    assert provider.embed("RAG")[ai_axis] > 0.0
    assert provider.embed("LLM")[ai_axis] > 0.0
    assert provider.embed("HTML")[data_axis] > 0.0
    assert provider.embed("paragraph")[ai_axis] == 0.0
    assert provider.embed("xhtml")[data_axis] == 0.0


def test_non_devops_documents_do_not_get_ci_evidence_from_city_field() -> None:
    provider = ControlledEmbeddingProvider()
    devops_axis = provider.CONCEPT_AXES.index("devops")
    jobs = build_evaluation_jobs()
    documents = [build_job_document(job) for job in jobs]

    non_devops_documents = [document for document in documents if document.id != 4]
    assert all(
        provider.embed(document.content)[devops_axis] == 0.0
        for document in non_devops_documents
    )
    assert provider.embed(documents[3].content)[devops_axis] > 0.0


def test_embedding_api_only_accepts_text_and_not_identity_arguments() -> None:
    provider = ControlledEmbeddingProvider()

    assert list(inspect.signature(provider.embed).parameters) == ["text"]
    assert list(inspect.signature(provider.embed_batch).parameters) == ["texts"]
    with pytest.raises(TypeError):
        provider.embed("大模型 Agent RAG", expected_job_id=5)  # type: ignore[call-arg]


def test_explicit_job_fixtures_have_stable_ids_and_sample_semantics() -> None:
    jobs = build_evaluation_jobs()
    documents = [build_job_document(job) for job in jobs]

    assert [job.id for job in jobs] == [1, 2, 3, 4, 5, 6]
    assert [job.title for job in jobs] == [
        "Python后端实习生",
        "自动化测试实习生",
        "数据采集实习生",
        "DevOps实习生",
        "AI应用开发实习生",
        "软件测试实习生",
    ]
    assert "FastAPI后端接口开发" in documents[0].content
    assert "Pytest完成接口自动化测试" in documents[1].content
    assert "网页数据采集、HTML解析、数据清洗" in documents[2].content
    assert "Linux服务器维护、Docker部署和CI" in documents[3].content
    assert "大模型应用、工具调用和RAG" in documents[4].content
    assert "功能测试、接口验证、缺陷记录和回归测试" in documents[5].content


@pytest.mark.parametrize("case_id", [
    "retrieval_ai_rag",
    "retrieval_backend_api",
    "retrieval_automated_testing",
    "retrieval_data_crawling",
    "retrieval_devops",
    "retrieval_functional_testing",
])
def test_authoritative_case_has_semantic_top_one_and_strict_margin(
    case_id: str,
) -> None:
    case = next(case for case in load_retrieval_cases() if case.case_id == case_id)
    retriever = build_controlled_retriever()

    results = retriever.search(case.query, case.top_k)

    assert isinstance(retriever, JobKnowledgeRetriever)
    assert results[0].document.id == case.expected_job_id
    assert results[0].score > results[1].score


def test_all_authoritative_cases_use_production_retriever_path() -> None:
    retriever = build_controlled_retriever()

    for case in load_retrieval_cases():
        results = retriever.search(case.query, case.top_k)
        assert results[0].document.id == case.expected_job_id
        assert results[0].score > results[1].score
