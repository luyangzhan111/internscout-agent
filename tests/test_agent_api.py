"""Offline HTTP integration tests for the Stage 9 agent endpoint."""

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
from app.api.dependencies import get_model_client
from app.database import (
    create_database_engine,
    create_session_factory,
    get_session,
    save_jobs,
)
from app.main import app
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
) -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    """Provide a TestClient and session factory bound to one temp database."""

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
