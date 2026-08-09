"""测试岗位详情FastAPI接口。"""

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
    save_jobs,
)
from app.main import app
from app.schemas.job import JobCreate
from app.services import process_jobs


def create_job(
    **overrides: object,
) -> JobCreate:
    """创建用于岗位详情API测试的合法岗位。"""

    job_data = {
        "title": "Python后端实习生",
        "company": "星河科技",
        "city": "深圳市",
        "salary": "150-200元/天",
        "description": "负责Python后端接口开发。",
        "skills": [
            "python",
            "fastapi",
            "sql",
        ],
        "source": "mock",
        "source_url": "https://example.com/jobs/001",
        "published_at": "2026-07-20",
    }

    job_data.update(
        overrides
    )

    return JobCreate(
        **job_data
    )


@pytest.fixture
def detail_api_client(
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    """创建使用临时SQLite数据库的详情API客户端。"""

    database_path = (
        tmp_path
        / "job-detail-api-test.db"
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
        """为详情接口提供临时数据库会话。"""

        with session_factory() as session:
            yield session

    app.state.database_engine = engine

    app.dependency_overrides[
        get_session
    ] = override_get_session

    try:
        with TestClient(app) as client:
            raw_jobs = [
                create_job(
                    title="Python后端实习生",
                    company="星河科技",
                    city="深圳市",
                    source_url=(
                        "https://example.com/jobs/001"
                    ),
                ),
                create_job(
                    title="Agent开发实习生",
                    company="未来智能",
                    city="上海市",
                    salary=None,
                    skills=[
                        "python",
                        "llm",
                        "rag",
                    ],
                    source_url=(
                        "https://example.com/jobs/002"
                    ),
                    published_at=None,
                ),
            ]

            processed_jobs = process_jobs(
                raw_jobs
            )

            with session_factory() as setup_session:
                save_jobs(
                    setup_session,
                    processed_jobs,
                )

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


def test_get_job_detail_returns_requested_job(
    detail_api_client: TestClient,
) -> None:
    """存在的岗位ID应返回完整岗位详情。"""

    response = detail_api_client.get(
        "/api/jobs/2"
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["id"] == 2
    assert response_data["title"] == (
        "Agent开发实习生"
    )
    assert response_data["company"] == (
        "未来智能"
    )
    assert response_data["city"] == "上海"
    assert response_data["salary"] is None
    assert response_data["skills"] == [
        "Python",
        "LLM",
        "RAG",
    ]
    assert (
        response_data["published_at"]
        is None
    )

    assert "identity_key" not in response_data


def test_get_job_detail_returns_404_for_missing_job(
    detail_api_client: TestClient,
) -> None:
    """不存在的岗位ID应返回404。"""

    response = detail_api_client.get(
        "/api/jobs/999999"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "岗位不存在",
    }


@pytest.mark.parametrize(
    "job_id",
    [
        "0",
        "-1",
        "not-a-number",
    ],
)
def test_get_job_detail_rejects_invalid_id(
    detail_api_client: TestClient,
    job_id: str,
) -> None:
    """非法岗位ID应由FastAPI返回422。"""

    response = detail_api_client.get(
        f"/api/jobs/{job_id}"
    )

    assert response.status_code == 422
