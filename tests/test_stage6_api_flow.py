"""测试阶段6完整FastAPI岗位业务闭环。"""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.database import (
    create_database_engine,
    create_session_factory,
    database_engine,
    get_session,
)
from app.main import app


@pytest.fixture
def stage6_client(
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    """创建使用全新临时SQLite数据库的阶段6客户端。"""

    database_path = (
        tmp_path
        / "stage6-flow-test.db"
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
        """为阶段6接口提供临时数据库会话。"""

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
            assert inspect(engine).get_table_names() == [
                "jobs",
            ]

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


def test_stage6_complete_api_flow(
    stage6_client: TestClient,
) -> None:
    """从空库开始完整执行健康检查、采集、查询和详情流程。"""

    health_response = stage6_client.get(
        "/api/health"
    )

    assert health_response.status_code == 200
    assert health_response.json() == {
        "status": "ok",
        "database": "ok",
    }

    empty_jobs_response = stage6_client.get(
        "/api/jobs"
    )

    assert empty_jobs_response.status_code == 200
    assert empty_jobs_response.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 10,
        "pages": 0,
    }

    crawl_response = stage6_client.post(
        "/api/crawl"
    )

    assert crawl_response.status_code == 200
    assert crawl_response.json() == {
        "processed_count": 6,
        "database_total": 6,
    }

    jobs_response = stage6_client.get(
        "/api/jobs"
    )

    assert jobs_response.status_code == 200

    jobs_data = jobs_response.json()

    assert jobs_data["total"] == 6
    assert jobs_data["page"] == 1
    assert jobs_data["page_size"] == 10
    assert jobs_data["pages"] == 1
    assert len(jobs_data["items"]) == 6

    first_job = jobs_data["items"][0]

    assert first_job["id"] >= 1
    assert first_job["city"] == "深圳"
    assert "identity_key" not in first_job

    detail_response = stage6_client.get(
        f"/api/jobs/{first_job['id']}"
    )

    assert detail_response.status_code == 200
    assert detail_response.json() == first_job


def test_stage6_filter_and_pagination_flow(
    stage6_client: TestClient,
) -> None:
    """采集完成后筛选和分页接口应能组合工作。"""

    crawl_response = stage6_client.post(
        "/api/crawl"
    )

    assert crawl_response.status_code == 200

    city_response = stage6_client.get(
        "/api/jobs",
        params={
            "city": "深圳市",
        },
    )

    assert city_response.status_code == 200

    city_data = city_response.json()

    assert city_data["total"] == 2

    assert all(
        item["city"] == "深圳"
        for item in city_data["items"]
    )

    skill_response = stage6_client.get(
        "/api/jobs",
        params={
            "skill": "Python",
            "page": 1,
            "page_size": 2,
        },
    )

    assert skill_response.status_code == 200

    skill_data = skill_response.json()

    assert skill_data["total"] >= 2
    assert skill_data["page"] == 1
    assert skill_data["page_size"] == 2
    assert len(skill_data["items"]) == 2

    assert all(
        "Python" in item["skills"]
        for item in skill_data["items"]
    )


def test_stage6_repeated_crawl_keeps_database_idempotent(
    stage6_client: TestClient,
) -> None:
    """完整HTTP链路重复执行采集时数据库数量不应增长。"""

    first_response = stage6_client.post(
        "/api/crawl"
    )

    second_response = stage6_client.post(
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

    jobs_response = stage6_client.get(
        "/api/jobs"
    )

    assert jobs_response.status_code == 200
    assert jobs_response.json()["total"] == 6
