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
