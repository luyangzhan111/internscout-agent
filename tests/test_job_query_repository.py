"""测试岗位筛选、统计和分页查询。"""

from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.database import (
    create_database_engine,
    create_session_factory,
    init_database,
    query_jobs,
    save_jobs,
)
from app.schemas.job import JobCreate
from app.services import process_jobs


def create_job(
    **overrides: object,
) -> JobCreate:
    """创建用于岗位查询测试的合法岗位。"""

    job_data = {
        "title": "Python后端实习生",
        "company": "星河科技",
        "city": "深圳",
        "salary": "150-200元/天",
        "description": "负责岗位相关工作。",
        "skills": [
            "Python",
            "FastAPI",
            "SQL",
        ],
        "source": "mock",
        "source_url": (
            "https://example.com/jobs/001"
        ),
        "published_at": "2026-07-20",
    }
    job_data.update(overrides)

    return JobCreate(**job_data)


@pytest.fixture
def database_session(
    tmp_path: Path,
) -> Generator[Session, None, None]:
    """创建包含测试岗位的临时数据库会话。"""

    database_path = tmp_path / "query-test.db"
    database_url = (
        f"sqlite:///{database_path.as_posix()}"
    )

    engine = create_database_engine(database_url)

    try:
        init_database(engine)

        session_factory = create_session_factory(
            engine
        )

        jobs = [
            create_job(
                title="Python后端实习生",
                company="星河科技",
                city="深圳",
                skills=[
                    "Python",
                    "FastAPI",
                    "SQL",
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
                    "Python",
                    "pytest",
                    "HTTP",
                ],
                source_url=(
                    "https://example.com/jobs/002"
                ),
            ),
            create_job(
                title="Agent开发实习生",
                company="未来智能",
                city="上海",
                skills=[
                    "Python",
                    "LLM",
                    "RAG",
                ],
                source_url=(
                    "https://example.com/jobs/003"
                ),
            ),
            create_job(
                title="数据分析实习生",
                company="云帆科技",
                city="广州",
                skills=[
                    "Python",
                    "SQL",
                    "Pandas",
                ],
                source_url=(
                    "https://example.com/jobs/004"
                ),
            ),
            create_job(
                title="前端开发实习生",
                company=" Example   Tech ",
                city="深圳",
                skills=[
                    "HTML",
                    "JavaScript",
                    "NoSQL",
                ],
                source_url=(
                    "https://example.com/jobs/005"
                ),
            ),
        ]

        processed_jobs = process_jobs(jobs)

        with session_factory() as setup_session:
            save_jobs(
                setup_session,
                processed_jobs,
            )

        with session_factory() as session:
            yield session
    finally:
        engine.dispose()


def test_query_jobs_returns_paginated_primary_key_order(
    database_session: Session,
) -> None:
    """分页查询应按主键稳定排序。"""

    items, total = query_jobs(
        database_session,
        page=2,
        page_size=2,
    )

    assert total == 5
    assert [job.id for job in items] == [3, 4]
    assert [job.title for job in items] == [
        "Agent开发实习生",
        "数据分析实习生",
    ]


def test_query_jobs_filters_normalized_city(
    database_session: Session,
) -> None:
    """城市别名应匹配标准化后的数据库城市。"""

    items, total = query_jobs(
        database_session,
        city=" 深圳市 ",
    )

    assert total == 3
    assert [job.title for job in items] == [
        "Python后端实习生",
        "自动化测试实习生",
        "前端开发实习生",
    ]


def test_query_jobs_filters_company_case_insensitively(
    database_session: Session,
) -> None:
    """公司筛选应统一空格并忽略英文大小写。"""

    items, total = query_jobs(
        database_session,
        company=" example   tech ",
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].company == "Example Tech"


def test_query_jobs_filters_exact_json_skill(
    database_session: Session,
) -> None:
    """技能筛选应精确匹配JSON数组成员。"""

    items, total = query_jobs(
        database_session,
        skill="sql",
    )

    assert total == 2
    assert [job.title for job in items] == [
        "Python后端实习生",
        "数据分析实习生",
    ]

    assert all(
        "NoSQL" not in job.skills
        for job in items
    )


def test_query_jobs_combines_filters(
    database_session: Session,
) -> None:
    """多个筛选条件应同时生效。"""

    items, total = query_jobs(
        database_session,
        city="深圳市",
        company="星河科技",
        skill="python",
    )

    assert total == 2
    assert [job.title for job in items] == [
        "Python后端实习生",
        "自动化测试实习生",
    ]


def test_query_jobs_keeps_total_when_page_is_empty(
    database_session: Session,
) -> None:
    """超出结果范围的页码应返回空列表和正确总数。"""

    items, total = query_jobs(
        database_session,
        page=10,
        page_size=2,
    )

    assert items == []
    assert total == 5


def test_query_jobs_handles_extremely_large_page(
    database_session: Session,
) -> None:
    """极大页码应返回空结果而不是触发SQLite溢出。"""

    items, total = query_jobs(
        database_session,
        page=10**18,
        page_size=100,
    )

    assert items == []
    assert total == 5


@pytest.mark.parametrize(
    "filters",
    [
        {"city": "   "},
        {"company": "   "},
        {"skill": "   "},
    ],
)
def test_query_jobs_rejects_blank_filters(
    database_session: Session,
    filters: dict[str, str],
) -> None:
    """Repository不应把空白筛选当成无筛选条件。"""

    with pytest.raises(ValueError):
        query_jobs(
            database_session,
            **filters,
        )


@pytest.mark.parametrize(
    ("page", "page_size"),
    [
        (0, 10),
        (1, 0),
        (1, 101),
    ],
)
def test_query_jobs_rejects_invalid_pagination(
    database_session: Session,
    page: int,
    page_size: int,
) -> None:
    """Repository应拒绝无效分页参数。"""

    with pytest.raises(ValueError):
        query_jobs(
            database_session,
            page=page,
            page_size=page_size,
        )
