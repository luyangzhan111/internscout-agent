"""测试岗位查询FastAPI接口。"""

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
    save_jobs,
)
from app.main import app
from app.schemas.job import JobCreate
from app.services import process_jobs


def create_job(
    **overrides: object,
) -> JobCreate:
    """创建用于岗位API测试的合法岗位。"""

    job_data = {
        "title": "Python后端实习生",
        "company": "星河科技",
        "city": "深圳市",
        "salary": "150-200元/天",
        "description": "负责岗位相关工作。",
        "skills": [
            "python",
            "fastapi",
            "sql",
        ],
        "source": "mock",
        "source_url": (
            "https://example.com/jobs/001"
        ),
        "published_at": "2026-07-20",
    }
    job_data.update(overrides)

    return JobCreate(**job_data)


def create_api_jobs() -> list[JobCreate]:
    """创建岗位API测试使用的原始岗位列表。"""

    return [
        create_job(
            title="Python后端实习生",
            company="星河科技",
            city="深圳市",
            skills=[
                "python",
                "fastapi",
                "sql",
            ],
            source_url=(
                "https://example.com/jobs/001"
            ),
        ),
        create_job(
            title="自动化测试实习生",
            company="星河科技",
            city="深圳",
            skills=[
                "python",
                "pytest",
                "http",
            ],
            source_url=(
                "https://example.com/jobs/002"
            ),
        ),
        create_job(
            title="Agent开发实习生",
            company="未来智能",
            city="上海市",
            skills=[
                "python",
                "llm",
                "rag",
            ],
            source_url=(
                "https://example.com/jobs/003"
            ),
        ),
        create_job(
            title="数据分析实习生",
            company="云帆科技",
            city="广州市",
            skills=[
                "python",
                "sql",
                "Pandas",
            ],
            source_url=(
                "https://example.com/jobs/004"
            ),
        ),
        create_job(
            title="前端开发实习生",
            company=" Example   Tech ",
            city="深圳市",
            skills=[
                "html",
                "JavaScript",
                "NoSQL",
            ],
            source_url=(
                "https://example.com/jobs/005"
            ),
        ),
    ]


@pytest.fixture
def api_client(
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    """创建连接临时SQLite数据库的API测试客户端。"""

    database_path = tmp_path / "job-api-test.db"
    database_url = (
        f"sqlite:///{database_path.as_posix()}"
    )

    engine = create_database_engine(database_url)

    try:
        session_factory = create_session_factory(
            engine
        )

        def override_get_session(
        ) -> Generator[Session, None, None]:
            """为API请求提供临时数据库会话。"""

            with session_factory() as session:
                yield session

        app.state.database_engine = engine
        app.dependency_overrides[get_session] = (
            override_get_session
        )

        with TestClient(app) as client:
            processed_jobs = process_jobs(
                create_api_jobs()
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
        app.state.database_engine = database_engine
        engine.dispose()


def test_lifespan_initializes_fresh_database(
    tmp_path: Path,
) -> None:
    """全新数据库启动后首次查询应正常返回空列表。"""

    database_path = tmp_path / "fresh-api-test.db"
    database_url = (
        f"sqlite:///{database_path.as_posix()}"
    )

    engine = create_database_engine(database_url)

    try:
        session_factory = create_session_factory(
            engine
        )

        def override_get_session(
        ) -> Generator[Session, None, None]:
            with session_factory() as session:
                yield session

        app.state.database_engine = engine
        app.dependency_overrides[get_session] = (
            override_get_session
        )

        assert database_path.exists() is False

        with TestClient(app) as client:
            assert database_path.exists() is True
            assert inspect(
                engine
            ).get_table_names() == ["jobs"]

            response = client.get("/api/jobs")

            assert response.status_code == 200
            assert response.json() == {
                "items": [],
                "total": 0,
                "page": 1,
                "page_size": 10,
                "pages": 0,
            }
    finally:
        app.dependency_overrides.pop(
            get_session,
            None,
        )
        app.state.database_engine = database_engine
        engine.dispose()


def test_get_jobs_returns_default_page(
    api_client: TestClient,
) -> None:
    """默认查询应返回全部测试岗位和分页信息。"""

    response = api_client.get("/api/jobs")

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["total"] == 5
    assert response_data["page"] == 1
    assert response_data["page_size"] == 10
    assert response_data["pages"] == 1
    assert len(response_data["items"]) == 5

    assert [
        item["title"]
        for item in response_data["items"]
    ] == [
        "Python后端实习生",
        "自动化测试实习生",
        "Agent开发实习生",
        "数据分析实习生",
        "前端开发实习生",
    ]

    assert all(
        "identity_key" not in item
        for item in response_data["items"]
    )


def test_get_jobs_supports_pagination(
    api_client: TestClient,
) -> None:
    """分页接口应返回正确数据和总页数。"""

    response = api_client.get(
        "/api/jobs",
        params={
            "page": 2,
            "page_size": 2,
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["total"] == 5
    assert response_data["page"] == 2
    assert response_data["page_size"] == 2
    assert response_data["pages"] == 3

    assert [
        item["title"]
        for item in response_data["items"]
    ] == [
        "Agent开发实习生",
        "数据分析实习生",
    ]


def test_get_jobs_filters_normalized_city(
    api_client: TestClient,
) -> None:
    """城市别名应匹配标准化后的岗位城市。"""

    response = api_client.get(
        "/api/jobs",
        params={
            "city": " 深圳市 ",
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["total"] == 3
    assert [
        item["title"]
        for item in response_data["items"]
    ] == [
        "Python后端实习生",
        "自动化测试实习生",
        "前端开发实习生",
    ]

    assert all(
        item["city"] == "深圳"
        for item in response_data["items"]
    )


def test_get_jobs_filters_company_case_insensitively(
    api_client: TestClient,
) -> None:
    """公司筛选应统一空格并忽略英文大小写。"""

    response = api_client.get(
        "/api/jobs",
        params={
            "company": " example   tech ",
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["total"] == 1
    assert len(response_data["items"]) == 1
    assert response_data["items"][0]["company"] == (
        "Example Tech"
    )


def test_get_jobs_filters_exact_json_skill(
    api_client: TestClient,
) -> None:
    """技能筛选应精确匹配JSON数组成员。"""

    response = api_client.get(
        "/api/jobs",
        params={
            "skill": "sql",
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["total"] == 2

    assert [
        item["title"]
        for item in response_data["items"]
    ] == [
        "Python后端实习生",
        "数据分析实习生",
    ]

    assert all(
        "NoSQL" not in item["skills"]
        for item in response_data["items"]
    )


def test_get_jobs_combines_filters(
    api_client: TestClient,
) -> None:
    """城市、公司和技能条件应同时生效。"""

    response = api_client.get(
        "/api/jobs",
        params={
            "city": "深圳市",
            "company": "星河科技",
            "skill": "python",
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["total"] == 2
    assert response_data["pages"] == 1

    assert [
        item["title"]
        for item in response_data["items"]
    ] == [
        "Python后端实习生",
        "自动化测试实习生",
    ]


def test_get_jobs_keeps_total_when_page_is_empty(
    api_client: TestClient,
) -> None:
    """超出范围的页码应返回空列表和正确总数。"""

    response = api_client.get(
        "/api/jobs",
        params={
            "page": 10,
            "page_size": 2,
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["items"] == []
    assert response_data["total"] == 5
    assert response_data["page"] == 10
    assert response_data["page_size"] == 2
    assert response_data["pages"] == 3


def test_get_jobs_handles_extremely_large_page(
    api_client: TestClient,
) -> None:
    """极大合法页码应返回空页而不是500。"""

    response = api_client.get(
        "/api/jobs",
        params={
            "page": 10**18,
            "page_size": 100,
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["items"] == []
    assert response_data["total"] == 5
    assert response_data["page"] == 10**18
    assert response_data["page_size"] == 100
    assert response_data["pages"] == 1


def test_get_jobs_returns_zero_pages_for_no_matches(
    api_client: TestClient,
) -> None:
    """没有符合条件的岗位时总页数应为零。"""

    response = api_client.get(
        "/api/jobs",
        params={
            "city": "不存在的城市",
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["items"] == []
    assert response_data["total"] == 0
    assert response_data["page"] == 1
    assert response_data["page_size"] == 10
    assert response_data["pages"] == 0


@pytest.mark.parametrize(
    "parameter_name",
    [
        "city",
        "company",
        "skill",
    ],
)
def test_get_jobs_rejects_blank_filters(
    api_client: TestClient,
    parameter_name: str,
) -> None:
    """纯空格筛选参数应返回422。"""

    response = api_client.get(
        "/api/jobs",
        params={
            parameter_name: "   ",
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "query_params",
    [
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
    ],
)
def test_get_jobs_rejects_invalid_pagination(
    api_client: TestClient,
    query_params: dict[str, int],
) -> None:
    """无效分页参数应由FastAPI返回422。"""

    response = api_client.get(
        "/api/jobs",
        params=query_params,
    )

    assert response.status_code == 422
