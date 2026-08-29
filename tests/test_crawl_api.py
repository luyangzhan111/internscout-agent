"""测试岗位采集FastAPI接口。"""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import (
    create_database_engine,
    create_session_factory,
    database_engine,
    get_session,
)
from app.main import app
from app.rag.embedding import FakeEmbeddingProvider
from app.rag.runtime import RetrievalRuntime
from app.api.dependencies import get_retrieval_runtime


@pytest.fixture
def crawl_api_client(
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    """创建使用全新临时SQLite数据库的采集API客户端。"""

    database_path = (
        tmp_path
        / "crawl-api-test.db"
    )

    database_url = (
        f"sqlite:///{database_path.as_posix()}"
    )

    engine = create_database_engine(
        database_url
    )

    session_factory = (
        create_session_factory(
            engine
        )
    )

    def override_get_session(
    ) -> Generator[
        Session,
        None,
        None,
    ]:
        """为采集API提供临时数据库会话。"""

        with session_factory() as session:
            yield session

    app.state.database_engine = engine

    app.dependency_overrides[
        get_session
    ] = override_get_session

    try:
        assert database_path.exists() is False

        with TestClient(app) as client:
            assert database_path.exists() is True

            yield client

    finally:
        app.dependency_overrides.pop(
            get_session,
            None,
        )

        app.state.database_engine = (
            database_engine
        )

        engine.dispose()


def test_post_crawl_ingests_mock_jobs(
    crawl_api_client: TestClient,
) -> None:
    """全新数据库应能通过采集接口写入模拟岗位。"""

    before_response = crawl_api_client.get(
        "/api/jobs"
    )

    assert before_response.status_code == 200
    assert before_response.json()["total"] == 0

    crawl_response = crawl_api_client.post(
        "/api/crawl"
    )

    assert crawl_response.status_code == 200
    assert crawl_response.json() == {
        "processed_count": 6,
        "database_total": 6,
    }

    jobs_response = crawl_api_client.get(
        "/api/jobs"
    )

    assert jobs_response.status_code == 200

    jobs_data = jobs_response.json()

    assert jobs_data["total"] == 6
    assert len(jobs_data["items"]) == 6


def test_lifespan_mounts_application_retrieval_runtime_state(
    crawl_api_client: TestClient,
) -> None:
    assert hasattr(app.state, "retrieval_runtime")


def test_successful_crawl_marks_runtime_dirty_without_rebuilding(
    crawl_api_client: TestClient,
) -> None:
    runtime = RetrievalRuntime(
        embedding_provider=FakeEmbeddingProvider(),
    )
    runtime.rebuild([])
    assert runtime.is_ready is True

    previous = app.dependency_overrides.get(
        get_retrieval_runtime,
    )
    app.dependency_overrides[get_retrieval_runtime] = (
        lambda: runtime
    )
    try:
        response = crawl_api_client.post(
            "/api/crawl"
        )
    finally:
        if previous is None:
            app.dependency_overrides.pop(
                get_retrieval_runtime,
                None,
            )
        else:
            app.dependency_overrides[get_retrieval_runtime] = previous

    assert response.status_code == 200
    assert runtime.is_dirty is True
    assert runtime.is_ready is False


def test_failed_crawl_does_not_mark_clean_runtime_dirty(
    crawl_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = RetrievalRuntime(
        embedding_provider=FakeEmbeddingProvider(),
    )
    runtime.rebuild([])

    def fail_ingestion(*args: object, **kwargs: object) -> list[object]:
        raise RuntimeError("crawl failed")

    monkeypatch.setattr(
        "app.api.routes.crawl.ingest_jobs",
        fail_ingestion,
    )
    previous = app.dependency_overrides.get(
        get_retrieval_runtime,
    )
    app.dependency_overrides[get_retrieval_runtime] = (
        lambda: runtime
    )
    try:
        with pytest.raises(RuntimeError, match="crawl failed"):
            crawl_api_client.post(
                "/api/crawl"
            )
    finally:
        if previous is None:
            app.dependency_overrides.pop(
                get_retrieval_runtime,
                None,
            )
        else:
            app.dependency_overrides[get_retrieval_runtime] = previous

    assert runtime.is_dirty is False


def test_post_crawl_is_idempotent(
    crawl_api_client: TestClient,
) -> None:
    """重复采集同一批岗位不应增加数据库记录。"""

    first_response = crawl_api_client.post(
        "/api/crawl"
    )

    second_response = crawl_api_client.post(
        "/api/crawl"
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    assert first_response.json() == {
        "processed_count": 6,
        "database_total": 6,
    }

    assert second_response.json() == {
        "processed_count": 6,
        "database_total": 6,
    }

    jobs_response = crawl_api_client.get(
        "/api/jobs"
    )

    assert jobs_response.status_code == 200
    assert jobs_response.json()["total"] == 6


def test_post_crawl_saves_normalized_jobs(
    crawl_api_client: TestClient,
) -> None:
    """采集接口保存的数据应经过清洗和标准化。"""

    crawl_response = crawl_api_client.post(
        "/api/crawl"
    )

    assert crawl_response.status_code == 200

    jobs_response = crawl_api_client.get(
        "/api/jobs"
    )

    assert jobs_response.status_code == 200

    items = jobs_response.json()["items"]

    assert [
        item["city"]
        for item in items
    ] == [
        "深圳",
        "广州",
        "上海",
        "深圳",
        "北京",
        "东莞",
    ]

    assert items[1]["skills"] == [
        "Python",
        "pytest",
        "HTTP",
        "SQL",
    ]

    assert items[2]["skills"] == [
        "Python",
        "Requests",
        "Beautiful Soup",
        "SQL",
    ]


def test_crawl_endpoint_requires_post(
    crawl_api_client: TestClient,
) -> None:
    """采集接口不应接受GET请求。"""

    response = crawl_api_client.get(
        "/api/crawl"
    )

    assert response.status_code == 405
