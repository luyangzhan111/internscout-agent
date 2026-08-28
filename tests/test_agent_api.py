"""Offline HTTP integration tests for the Stage 9 agent endpoint."""

import json
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.agent.contracts import (
    FinalAnswerResponse,
    ModelRequest,
    ModelResponse,
    ToolCall,
    ToolCallResponse,
)
from app.agent.model_client import ModelClient
from app.api.dependencies import (
    create_retrieval_runtime,
    get_model_client,
    get_retrieval_runtime,
)
from app.database import (
    create_database_engine,
    create_session_factory,
    get_session,
    save_jobs,
)
from app.main import app
from app.rag.embedding import EmbeddingProvider, FakeEmbeddingProvider
from app.rag.runtime import RetrievalRuntime
from app.schemas.job import JobCreate
from app.services import process_jobs
from tests.agent.fakes.fake_model_client import FakeModelClient


_MISSING = object()


def create_job(**overrides: object) -> JobCreate:
    """Create one valid raw job for the integration database."""

    data: dict[str, object] = {
        "title": "Python后端实习生",
        "company": "星河科技",
        "city": "深圳市",
        "salary": "150-200元/天",
        "description": "负责岗位相关工作。",
        "skills": ["python", "fastapi", "sql"],
        "source": "stage9-test",
        "source_url": "https://example.com/stage9/1",
        "published_at": "2026-08-10",
    }
    data.update(overrides)
    return JobCreate(**data)


@pytest.fixture
def agent_api_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    """Provide a TestClient and session factory bound to one temp database."""

    monkeypatch.delenv(
        "INTERNSCOUT_EMBEDDING_API_KEY",
        raising=False,
    )
    monkeypatch.delenv(
        "INTERNSCOUT_EMBEDDING_BASE_URL",
        raising=False,
    )
    monkeypatch.delenv(
        "INTERNSCOUT_EMBEDDING_MODEL",
        raising=False,
    )
    monkeypatch.delenv(
        "INTERNSCOUT_EMBEDDING_DIMENSIONS",
        raising=False,
    )

    database_path = tmp_path / "agent-api-test.db"
    engine = create_database_engine(
        f"sqlite:///{database_path.as_posix()}"
    )
    session_factory = create_session_factory(engine)

    def override_get_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    previous_engine = getattr(
        app.state,
        "database_engine",
        _MISSING,
    )
    previous_session_override = app.dependency_overrides.get(
        get_session,
        _MISSING,
    )
    previous_model_override = app.dependency_overrides.get(
        get_model_client,
        _MISSING,
    )

    app.state.database_engine = engine
    app.dependency_overrides[get_session] = override_get_session

    try:
        with TestClient(app) as client:
            yield client, session_factory
    finally:
        if previous_session_override is _MISSING:
            app.dependency_overrides.pop(get_session, None)
        else:
            app.dependency_overrides[get_session] = previous_session_override

        if previous_model_override is _MISSING:
            app.dependency_overrides.pop(get_model_client, None)
        else:
            app.dependency_overrides[get_model_client] = previous_model_override

        if previous_engine is _MISSING:
            try:
                del app.state.database_engine
            except AttributeError:
                pass
        else:
            app.state.database_engine = previous_engine

        engine.dispose()


@contextmanager
def override_model_client(
    model_client: ModelClient,
) -> Generator[None, None, None]:
    """Override only the provider seam for one request or test."""

    previous = app.dependency_overrides.get(
        get_model_client,
        _MISSING,
    )
    app.dependency_overrides[get_model_client] = (
        lambda: model_client
    )

    try:
        yield
    finally:
        if previous is _MISSING:
            app.dependency_overrides.pop(get_model_client, None)
        else:
            app.dependency_overrides[get_model_client] = previous


@contextmanager
def override_retrieval_runtime(
    runtime: RetrievalRuntime | None,
) -> Generator[None, None, None]:
    """Override the application retrieval runtime for one test."""

    previous = app.dependency_overrides.get(
        get_retrieval_runtime,
        _MISSING,
    )
    app.dependency_overrides[get_retrieval_runtime] = (
        lambda: runtime
    )

    try:
        yield
    finally:
        if previous is _MISSING:
            app.dependency_overrides.pop(
                get_retrieval_runtime,
                None,
            )
        else:
            app.dependency_overrides[get_retrieval_runtime] = previous


class FailingEmbeddingProvider(EmbeddingProvider):
    """Test-local provider that never performs a network request."""

    def embed(self, text: str) -> list[float]:
        raise RuntimeError("embedding failed")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding failed")


class ToggleEmbeddingProvider(FakeEmbeddingProvider):
    """Fail only refresh batches after an old index has been built."""

    def __init__(self) -> None:
        super().__init__()
        self.fail_batch = False

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self.fail_batch:
            raise RuntimeError("refresh embedding failed")
        return super().embed_batch(texts)


def seed_jobs(
    session_factory: sessionmaker[Session],
    *jobs: JobCreate,
) -> list[int]:
    """Persist processed jobs and return their database IDs."""

    processed_jobs = process_jobs(list(jobs))
    with session_factory() as session:
        saved_jobs = save_jobs(session, processed_jobs)
        return [job.id for job in saved_jobs if job.id is not None]


def tool_call(
    *,
    call_id: str,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> ToolCallResponse:
    return ToolCallResponse(
        tool_call=ToolCall(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments or {},
        )
    )


def test_agent_query_returns_direct_final_answer(
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = agent_api_client
    fake_model = FakeModelClient(
        responses=[FinalAnswerResponse(answer="可以帮你查询岗位。")]
    )

    with override_model_client(fake_model):
        response = client.post(
            "/api/agent/query",
            json={"user_message": "你好"},
        )

    assert response.status_code == 200
    assert set(response.json()) == {
        "answer",
        "steps",
        "tool_execution_count",
    }
    assert response.json() == {
        "answer": "可以帮你查询岗位。",
        "steps": 1,
        "tool_execution_count": 0,
    }


def test_missing_embedding_configuration_disables_only_retrieval(
    monkeypatch: pytest.MonkeyPatch,
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    monkeypatch.delenv("INTERNSCOUT_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("INTERNSCOUT_EMBEDDING_BASE_URL", raising=False)

    assert create_retrieval_runtime() is None

    client, _ = agent_api_client
    fake_model = FakeModelClient(
        responses=[FinalAnswerResponse(answer="核心能力正常。")]
    )

    with override_retrieval_runtime(None):
        with override_model_client(fake_model):
            response = client.post(
                "/api/agent/query",
                json={"user_message": "查询岗位"},
            )

    assert response.status_code == 200
    assert [
        definition.name
        for definition in fake_model.requests[0].tools
    ] == [
        "search_jobs",
        "get_job_detail",
        "match_jobs",
    ]


def test_configured_retrieval_runtime_is_created_without_embedding_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INTERNSCOUT_EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv(
        "INTERNSCOUT_EMBEDDING_BASE_URL",
        "https://example.com/embeddings",
    )
    monkeypatch.setenv("INTERNSCOUT_EMBEDDING_MODEL", "test-model")
    monkeypatch.setenv("INTERNSCOUT_EMBEDDING_DIMENSIONS", "8")

    runtime = create_retrieval_runtime()

    assert isinstance(runtime, RetrievalRuntime)
    assert runtime.current_retriever is None
    assert runtime.is_dirty is True


def test_agent_retrieval_lazily_builds_and_reuses_clean_index(
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session_factory = agent_api_client
    seed_jobs(
        session_factory,
        create_job(source_url="https://example.com/retrieval/1"),
        create_job(
            title="Data Intern",
            source_url="https://example.com/retrieval/2",
        ),
    )
    runtime = RetrievalRuntime(
        embedding_provider=FakeEmbeddingProvider(),
    )
    first_model = FakeModelClient(
        responses=[
            tool_call(
                call_id="retrieve_001",
                tool_name="retrieve_job_knowledge",
                arguments={"query": "Python", "top_k": 5},
            ),
            FinalAnswerResponse(answer="已检索岗位。"),
        ]
    )

    with override_retrieval_runtime(runtime):
        with override_model_client(first_model):
            first_response = client.post(
                "/api/agent/query",
                json={"user_message": "检索 Python 岗位"},
            )

        assert first_response.status_code == 200
        assert runtime.is_ready is True
        assert runtime.is_dirty is False
        assert first_model.requests[0].tools[-1].name == (
            "retrieve_job_knowledge"
        )
        assert first_model.requests[1].tool_executions[0].result.success is True

        def unexpected_query(*args: object, **kwargs: object) -> object:
            raise AssertionError("clean retrieval index re-collected jobs")

        monkeypatch.setattr(
            "app.api.dependencies.RepositoryJobQueryAdapter.search_jobs",
            unexpected_query,
        )
        second_model = FakeModelClient(
            responses=[FinalAnswerResponse(answer="复用已建索引。")]
        )
        with override_model_client(second_model):
            second_response = client.post(
                "/api/agent/query",
                json={"user_message": "继续处理"},
            )

    assert second_response.status_code == 200


def test_agent_retrieval_empty_database_builds_ready_empty_index(
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = agent_api_client
    runtime = RetrievalRuntime(
        embedding_provider=FakeEmbeddingProvider(),
    )
    fake_model = FakeModelClient(
        responses=[
            tool_call(
                call_id="retrieve_empty_001",
                tool_name="retrieve_job_knowledge",
                arguments={"query": "Python"},
            ),
            FinalAnswerResponse(answer="没有岗位。"),
        ]
    )

    with override_retrieval_runtime(runtime):
        with override_model_client(fake_model):
            response = client.post(
                "/api/agent/query",
                json={"user_message": "检索岗位"},
            )

    assert response.status_code == 200
    assert runtime.is_ready is True
    assert fake_model.requests[1].tool_executions[0].result.data == []


def test_agent_first_retrieval_build_failure_disables_only_retrieval(
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = agent_api_client
    seed_jobs(
        session_factory,
        create_job(source_url="https://example.com/retrieval/failure"),
    )
    runtime = RetrievalRuntime(
        embedding_provider=FailingEmbeddingProvider(),
    )
    fake_model = FakeModelClient(
        responses=[FinalAnswerResponse(answer="核心工具仍可用。")]
    )

    with override_retrieval_runtime(runtime):
        with override_model_client(fake_model):
            response = client.post(
                "/api/agent/query",
                json={"user_message": "查询岗位"},
            )

    assert response.status_code == 200
    assert runtime.current_retriever is None
    assert runtime.is_dirty is True
    assert [
        definition.name
        for definition in fake_model.requests[0].tools
    ] == [
        "search_jobs",
        "get_job_detail",
        "match_jobs",
    ]


def test_agent_refresh_failure_falls_back_to_old_retriever(
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = agent_api_client
    seed_jobs(
        session_factory,
        create_job(source_url="https://example.com/retrieval/old"),
    )
    provider = ToggleEmbeddingProvider()
    runtime = RetrievalRuntime(
        embedding_provider=provider,
    )
    first_model = FakeModelClient(
        responses=[
            tool_call(
                call_id="retrieve_old_001",
                tool_name="retrieve_job_knowledge",
                arguments={"query": "Python"},
            ),
            FinalAnswerResponse(answer="旧索引已建立。"),
        ]
    )

    with override_retrieval_runtime(runtime):
        with override_model_client(first_model):
            first_response = client.post(
                "/api/agent/query",
                json={"user_message": "建立检索索引"},
            )

        assert first_response.status_code == 200
        old_retriever = runtime.current_retriever
        provider.fail_batch = True
        runtime.mark_dirty()

        second_model = FakeModelClient(
            responses=[
                tool_call(
                    call_id="retrieve_old_002",
                    tool_name="retrieve_job_knowledge",
                    arguments={"query": "Python"},
                ),
                FinalAnswerResponse(answer="继续使用旧索引。"),
            ]
        )
        with override_model_client(second_model):
            second_response = client.post(
                "/api/agent/query",
                json={"user_message": "再次检索岗位"},
            )

    assert second_response.status_code == 200
    assert runtime.current_retriever is old_retriever
    assert runtime.is_dirty is True
    assert second_model.requests[1].tool_executions[0].result.success is True


def test_agent_query_searches_jobs_through_real_database_path(
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = agent_api_client
    seed_jobs(
        session_factory,
        create_job(),
    )
    fake_model = FakeModelClient(
        responses=[
            tool_call(
                call_id="search_001",
                tool_name="search_jobs",
                arguments={"city": "深圳"},
            ),
            FinalAnswerResponse(answer="找到深圳岗位。"),
        ]
    )

    with override_model_client(fake_model):
        response = client.post(
            "/api/agent/query",
            json={"user_message": "找深圳岗位"},
        )

    assert response.status_code == 200
    assert response.json()["steps"] == 2
    assert response.json()["tool_execution_count"] == 1

    assert len(fake_model.requests) == 2
    execution = fake_model.requests[1].tool_executions[0]
    assert execution.result.success is True
    assert execution.result.tool_name == "search_jobs"
    assert execution.result.data["total"] == 1
    assert execution.result.data["items"][0]["title"] == "Python后端实习生"


def test_agent_query_gets_job_detail_through_real_database_path(
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = agent_api_client
    job_ids = seed_jobs(
        session_factory,
        create_job(title="Agent开发实习生"),
    )
    fake_model = FakeModelClient(
        responses=[
            tool_call(
                call_id="detail_001",
                tool_name="get_job_detail",
                arguments={"job_id": job_ids[0]},
            ),
            FinalAnswerResponse(answer="岗位详情已找到。"),
        ]
    )

    with override_model_client(fake_model):
        response = client.post(
            "/api/agent/query",
            json={"user_message": "查看岗位详情"},
        )

    assert response.status_code == 200
    assert response.json()["answer"] == "岗位详情已找到。"
    assert response.json()["steps"] == 2
    assert response.json()["tool_execution_count"] == 1
    assert response.json().keys() == {
        "answer",
        "steps",
        "tool_execution_count",
    }

    execution = fake_model.requests[1].tool_executions[0]
    assert execution.result.success is True
    assert execution.result.data["id"] == job_ids[0]
    assert execution.result.data["title"] == "Agent开发实习生"


def test_agent_query_matches_jobs_through_production_composition(
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = agent_api_client
    seed_jobs(
        session_factory,
        create_job(
            skills=["python", "fastapi"],
            source_url="https://example.com/stage11f/1",
        ),
        create_job(
            title="数据分析实习生",
            city="上海市",
            skills=["python", "sql"],
            source_url="https://example.com/stage11f/2",
        ),
    )
    fake_model = FakeModelClient(
        responses=[
            tool_call(
                call_id="match_001",
                tool_name="match_jobs",
                arguments={
                    "skills": ["Python"],
                    "preferred_cities": ["深圳"],
                    "top_k": 2,
                },
            ),
            FinalAnswerResponse(answer="已找到匹配岗位。"),
        ]
    )

    with override_model_client(fake_model):
        response = client.post(
            "/api/agent/query",
            json={"user_message": "匹配深圳的 Python 岗位"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "已找到匹配岗位。",
        "steps": 2,
        "tool_execution_count": 1,
    }
    assert len(fake_model.requests) == 2

    definitions = fake_model.requests[0].tools
    assert [definition.name for definition in definitions] == [
        "search_jobs",
        "get_job_detail",
        "match_jobs",
    ]
    match_definition = definitions[2]
    assert match_definition.parameters["required"] == ["skills"]
    assert set(match_definition.parameters["properties"]) == {
        "skills",
        "preferred_cities",
        "top_k",
    }

    executions = fake_model.requests[1].tool_executions
    assert len(executions) == 1
    execution = executions[0]
    assert execution.call.call_id == "match_001"
    assert execution.call.tool_name == "match_jobs"
    assert execution.result.success is True
    assert execution.result.error is None
    assert execution.result.tool_name == "match_jobs"
    assert len(execution.result.data) == 1
    assert execution.result.data[0]["job"]["title"] == (
        "Python后端实习生"
    )
    assert execution.result.data[0]["job"]["city"] == "深圳"
    assert execution.result.data[0]["matched_skills"] == ["Python"]
    json.dumps(execution.result.data, ensure_ascii=False)


def test_agent_query_excludes_recommendations_when_disabled(
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = agent_api_client
    fake_model = FakeModelClient(
        responses=[
            FinalAnswerResponse(answer="已完成岗位分析。")
        ]
    )

    with override_model_client(fake_model):
        response = client.post(
            "/api/agent/query",
            json={
                "user_message": "分析岗位",
                "include_recommendations": False,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "已完成岗位分析。",
        "steps": 1,
        "tool_execution_count": 0,
    }


def test_agent_query_returns_structured_recommendations_when_enabled(
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = agent_api_client
    seed_jobs(
        session_factory,
        create_job(
            skills=["python", "fastapi"],
        ),
    )
    fake_model = FakeModelClient(
        responses=[
            tool_call(
                call_id="demo_match_001",
                tool_name="match_jobs",
                arguments={
                    "skills": ["Python"],
                    "preferred_cities": ["深圳"],
                    "top_k": 1,
                },
            ),
            FinalAnswerResponse(answer="已找到匹配岗位。"),
        ]
    )

    with override_model_client(fake_model):
        response = client.post(
            "/api/agent/query",
            json={
                "user_message": "匹配深圳的 Python 岗位",
                "include_recommendations": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "已找到匹配岗位。"
    assert payload["steps"] == 2
    assert payload["tool_execution_count"] == 1
    assert len(payload["recommendations"]) == 1
    recommendation = payload["recommendations"][0]
    assert recommendation["job"]["title"] == "Python后端实习生"
    assert recommendation["job"]["company"] == "星河科技"
    assert recommendation["match_score"] == 50
    assert recommendation["matched_skills"] == ["Python"]
    assert recommendation["missing_skills"] == ["FastAPI"]
    assert recommendation["reason"] == "partial_match"
    assert "call" not in recommendation
    assert "result" not in recommendation


def test_agent_query_returns_empty_recommendations_without_match_jobs(
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = agent_api_client
    fake_model = FakeModelClient(
        responses=[
            FinalAnswerResponse(answer="没有执行匹配工具。")
        ]
    )

    with override_model_client(fake_model):
        response = client.post(
            "/api/agent/query",
            json={
                "user_message": "介绍一下系统",
                "include_recommendations": True,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "没有执行匹配工具。",
        "steps": 1,
        "tool_execution_count": 0,
        "recommendations": [],
    }


def test_agent_query_returns_empty_recommendations_for_match_failure(
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = agent_api_client
    fake_model = FakeModelClient(
        responses=[
            tool_call(
                call_id="demo_match_failure_001",
                tool_name="match_jobs",
                arguments={"skills": []},
            ),
            FinalAnswerResponse(answer="匹配输入无效。"),
        ]
    )

    with override_model_client(fake_model):
        response = client.post(
            "/api/agent/query",
            json={
                "user_message": "匹配岗位",
                "include_recommendations": True,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "匹配输入无效。",
        "steps": 2,
        "tool_execution_count": 1,
        "recommendations": [],
    }

    execution = fake_model.requests[1].tool_executions[0]
    assert execution.result.success is False
    assert execution.result.tool_name == "match_jobs"


def test_agent_query_recovers_from_real_tool_validation_failure(
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = agent_api_client
    fake_model = FakeModelClient(
        responses=[
            tool_call(
                call_id="invalid_001",
                tool_name="search_jobs",
                arguments={"page": 0},
            ),
            FinalAnswerResponse(answer="参数无效，我已完成说明。"),
        ]
    )

    with override_model_client(fake_model):
        response = client.post(
            "/api/agent/query",
            json={"user_message": "查找岗位"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "参数无效，我已完成说明。",
        "steps": 2,
        "tool_execution_count": 1,
    }
    execution = fake_model.requests[1].tool_executions[0]
    assert execution.result.success is False
    assert execution.result.error is not None
    assert execution.result.error.startswith("Invalid tool arguments:")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"user_message": ""},
        {"user_message": "   \t\n"},
        {"user_message": "hello", "unexpected": True},
    ],
)
def test_agent_query_rejects_invalid_request_payloads(
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
    payload: dict[str, object],
) -> None:
    client, _ = agent_api_client
    fake_model = FakeModelClient(
        responses=[
            FinalAnswerResponse(
                answer="不应生成此回答。"
            )
        ]
    )

    with override_model_client(fake_model):
        response = client.post(
            "/api/agent/query",
            json=payload,
        )

    assert response.status_code == 422
    assert fake_model.requests == []


def test_agent_query_returns_503_without_provider_configuration(
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = agent_api_client
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    get_model_client.cache_clear()

    try:
        response = client.post(
            "/api/agent/query",
            json={"user_message": "查询岗位"},
        )

        assert response.status_code == 503
        assert response.json() == {
            "detail": "Agent model service is unavailable."
        }
        assert "DEEPSEEK" not in response.text

        health_response = client.get("/api/health")
        assert health_response.status_code == 200
    finally:
        get_model_client.cache_clear()


def test_agent_query_returns_500_at_default_max_steps_boundary(
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = agent_api_client
    fake_model = FakeModelClient(
        responses=[
            tool_call(
                call_id=f"loop_{index}",
                tool_name="search_jobs",
                arguments={"page": 0},
            )
            for index in range(5)
        ]
    )

    with override_model_client(fake_model):
        response = client.post(
            "/api/agent/query",
            json={"user_message": "持续查询"},
        )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Agent service encountered an unexpected error."
    }
    assert "maximum step limit" not in response.text
    assert len(fake_model.requests) == 5


class ExplodingModelClient(ModelClient):
    """Test-local model boundary failure."""

    def generate(self, request: ModelRequest) -> ModelResponse:
        raise RuntimeError("sensitive model failure")


def test_agent_query_sanitizes_model_boundary_failure(
    agent_api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = agent_api_client

    with override_model_client(ExplodingModelClient()):
        response = client.post(
            "/api/agent/query",
            json={"user_message": "触发模型异常"},
        )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Agent service encountered an unexpected error."
    }
    assert "sensitive model failure" not in response.text
