"""测试岗位采集、处理与持久化工作流。"""

from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.crawlers import MockJobCrawler
from app.database import (
    create_database_engine,
    create_session_factory,
    init_database,
    list_jobs,
)
from app.schemas.job import JobCreate
from app.workflows import ingest_jobs


class StaticJobCrawler:
    """返回预设岗位数据的测试爬虫。"""

    def __init__(
        self,
        jobs: list[JobCreate],
    ) -> None:
        self.jobs = jobs

    def fetch_jobs(self) -> list[JobCreate]:
        """返回预设岗位列表的副本。"""

        return list(self.jobs)


def create_job(**overrides: object) -> JobCreate:
    """创建用于工作流测试的合法岗位。"""

    job_data = {
        "title": "Python后端实习生",
        "company": "星河科技",
        "city": "深圳市",
        "salary": "150-200元/天",
        "description": "负责Python后端接口开发。",
        "skills": [
            "python",
            "PYTEST",
        ],
        "source": "mock",
        "source_url": "https://example.com/jobs/001",
        "published_at": "2026-07-20",
    }
    job_data.update(overrides)

    return JobCreate(**job_data)


@pytest.fixture
def database_session(
    tmp_path: Path,
) -> Generator[Session, None, None]:
    """创建使用临时SQLite数据库的会话。"""

    database_path = tmp_path / "ingestion-test.db"
    database_url = (
        f"sqlite:///{database_path.as_posix()}"
    )

    engine = create_database_engine(database_url)
    init_database(engine)

    session_factory = create_session_factory(engine)

    with session_factory() as session:
        yield session

    engine.dispose()


def test_ingest_jobs_saves_cleaned_mock_jobs(
    database_session: Session,
) -> None:
    """模拟爬虫岗位应经过清洗后保存到数据库。"""

    saved_jobs = ingest_jobs(
        MockJobCrawler(),
        database_session,
    )
    stored_jobs = list_jobs(database_session)

    assert len(saved_jobs) == 6
    assert len(stored_jobs) == 6

    assert [
        job.city
        for job in stored_jobs
    ] == [
        "深圳",
        "广州",
        "上海",
        "深圳",
        "北京",
        "东莞",
    ]

    assert stored_jobs[1].skills == [
        "Python",
        "pytest",
        "HTTP",
        "SQL",
    ]

    assert stored_jobs[2].skills == [
        "Python",
        "Requests",
        "Beautiful Soup",
        "SQL",
    ]


def test_ingest_jobs_is_idempotent(
    database_session: Session,
) -> None:
    """重复执行相同采集任务不应增加数据库记录。"""

    first_result = ingest_jobs(
        MockJobCrawler(),
        database_session,
    )
    second_result = ingest_jobs(
        MockJobCrawler(),
        database_session,
    )

    stored_jobs = list_jobs(database_session)

    assert len(first_result) == 6
    assert len(second_result) == 6
    assert len(stored_jobs) == 6

    assert [
        job.id
        for job in first_result
    ] == [
        job.id
        for job in second_result
    ]


def test_ingest_jobs_handles_empty_result(
    database_session: Session,
) -> None:
    """爬虫没有返回岗位时应安全返回空列表。"""

    crawler = StaticJobCrawler([])

    saved_jobs = ingest_jobs(
        crawler,
        database_session,
    )

    assert saved_jobs == []
    assert list_jobs(database_session) == []


def test_ingest_jobs_keeps_first_duplicate_data(
    database_session: Session,
) -> None:
    """重复岗位应保留第一次出现并清洗后的数据。"""

    first = create_job(
        city="深圳市",
        skills=[
            "python",
            "PYTEST",
            "",
        ],
        source_url="https://example.com/jobs/first",
    )
    duplicate = create_job(
        city="深圳",
        skills=[
            "FastAPI",
        ],
        source_url="https://example.com/jobs/duplicate",
    )

    crawler = StaticJobCrawler([
        first,
        duplicate,
    ])

    saved_jobs = ingest_jobs(
        crawler,
        database_session,
    )
    stored_jobs = list_jobs(database_session)

    assert len(saved_jobs) == 1
    assert len(stored_jobs) == 1

    assert stored_jobs[0].city == "深圳"
    assert stored_jobs[0].skills == [
        "Python",
        "pytest",
    ]
    assert stored_jobs[0].source_url == (
        "https://example.com/jobs/first"
    )
