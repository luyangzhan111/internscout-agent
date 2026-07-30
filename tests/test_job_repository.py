"""测试岗位数据库保存、查询与重复处理。"""

from collections.abc import Generator
from pathlib import Path

import app.database.repository as repository_module
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import (
    JobModel,
    build_identity_key,
    create_database_engine,
    create_session_factory,
    init_database,
    job_model_from_schema,
    list_jobs,
    save_job,
    save_jobs,
)
from app.schemas.job import JobCreate


def create_job(**overrides: object) -> JobCreate:
    """创建用于数据库仓库测试的合法岗位。"""

    job_data = {
        "title": "Python后端实习生",
        "company": "星河科技",
        "city": "深圳",
        "salary": "150-200元/天",
        "description": "负责Python后端接口开发。",
        "skills": [
            "Python",
            "FastAPI",
            "SQL",
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
    """创建使用临时SQLite文件的测试会话。"""

    database_path = tmp_path / "repository-test.db"
    database_url = (
        f"sqlite:///{database_path.as_posix()}"
    )

    engine = create_database_engine(database_url)
    init_database(engine)

    session_factory = create_session_factory(engine)

    with session_factory() as session:
        yield session

    engine.dispose()


def test_build_identity_key_normalizes_identity() -> None:
    """身份键应忽略大小写、连续空格和城市别名。"""

    first = create_job(
        title="Python后端实习生",
        company="星河科技",
        city="深圳市",
    )
    second = create_job(
        title=" python后端实习生 ",
        company=" 星河科技 ",
        city="深圳",
        source_url="https://example.com/jobs/002",
    )

    assert build_identity_key(first) == (
        build_identity_key(second)
    )


def test_save_job_persists_all_fields(
    database_session: Session,
) -> None:
    """保存岗位后，数据库记录应包含完整字段。"""

    job = create_job()

    saved_job = save_job(
        database_session,
        job,
    )

    assert saved_job.id is not None
    assert saved_job.identity_key == (
        build_identity_key(job)
    )
    assert saved_job.title == job.title
    assert saved_job.company == job.company
    assert saved_job.city == job.city
    assert saved_job.salary == job.salary
    assert saved_job.description == job.description
    assert saved_job.skills == job.skills
    assert saved_job.source == job.source
    assert saved_job.source_url == job.source_url
    assert saved_job.published_at == job.published_at
    assert saved_job.created_at is not None


def test_save_job_preserves_optional_null_values(
    database_session: Session,
) -> None:
    """可选字段应当能够以NULL保存。"""

    job = create_job(
        salary=None,
        published_at=None,
    )

    saved_job = save_job(
        database_session,
        job,
    )

    assert saved_job.salary is None
    assert saved_job.published_at is None


def test_save_job_returns_existing_duplicate(
    database_session: Session,
) -> None:
    """重复保存同一岗位时不应创建第二条记录。"""

    first = create_job(
        source_url="https://example.com/jobs/001",
    )
    duplicate = create_job(
        city="深圳市",
        source_url="https://another-source.com/jobs/999",
    )

    first_saved = save_job(
        database_session,
        first,
    )
    duplicate_saved = save_job(
        database_session,
        duplicate,
    )

    row_count = database_session.scalar(
        select(func.count()).select_from(JobModel)
    )

    assert first_saved.id == duplicate_saved.id
    assert row_count == 1
    assert duplicate_saved.source_url == (
        "https://example.com/jobs/001"
    )


def test_save_jobs_preserves_first_seen_unique_order(
    database_session: Session,
) -> None:
    """批量保存应过滤重复岗位并保持首次出现顺序。"""

    first = create_job()
    duplicate = create_job(
        city="深圳市",
        source_url="https://example.com/jobs/duplicate",
    )
    second = create_job(
        title="自动化测试实习生",
        company="云帆软件",
        city="广州",
        skills=[
            "Python",
            "pytest",
            "SQL",
        ],
        source_url="https://example.com/jobs/002",
    )

    saved_jobs = save_jobs(
        database_session,
        [
            first,
            duplicate,
            second,
        ],
    )

    assert len(saved_jobs) == 2
    assert [
        job.title
        for job in saved_jobs
    ] == [
        "Python后端实习生",
        "自动化测试实习生",
    ]


def test_list_jobs_returns_primary_key_order(
    database_session: Session,
) -> None:
    """全部岗位查询结果应按照数据库主键排序。"""

    first = create_job(
        title="Python后端实习生",
        source_url="https://example.com/jobs/001",
    )
    second = create_job(
        title="Agent开发实习生",
        company="未来智能",
        city="上海",
        source_url="https://example.com/jobs/002",
    )

    save_job(database_session, first)
    save_job(database_session, second)

    stored_jobs = list_jobs(database_session)

    assert len(stored_jobs) == 2
    assert stored_jobs[0].id < stored_jobs[1].id
    assert [
        job.title
        for job in stored_jobs
    ] == [
        "Python后端实习生",
        "Agent开发实习生",
    ]


def test_database_enforces_identity_unique_constraint(
    database_session: Session,
) -> None:
    """数据库本身应拒绝相同身份键的重复记录。"""

    first = job_model_from_schema(
        create_job(
            source_url="https://example.com/jobs/001",
        )
    )
    duplicate = job_model_from_schema(
        create_job(
            city="深圳市",
            source_url="https://example.com/jobs/002",
        )
    )

    database_session.add(first)
    database_session.commit()

    database_session.add(duplicate)

    with pytest.raises(IntegrityError):
        database_session.commit()

    database_session.rollback()

    row_count = database_session.scalar(
        select(func.count()).select_from(JobModel)
    )

    assert row_count == 1

def test_save_job_reraises_unmatched_integrity_error(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """完整性错误无法匹配已有岗位时必须重新抛出。"""

    job = create_job()

    simulated_error = IntegrityError(
        "simulated insert",
        {},
        RuntimeError("simulated constraint failure"),
    )

    def raise_integrity_error() -> None:
        raise simulated_error

    with monkeypatch.context() as context:
        context.setattr(
            repository_module,
            "get_job_by_identity_key",
            lambda session, identity_key: None,
        )
        context.setattr(
            database_session,
            "commit",
            raise_integrity_error,
        )

        with pytest.raises(IntegrityError) as exc_info:
            repository_module.save_job(
                database_session,
                job,
            )

    assert exc_info.value is simulated_error

    row_count = database_session.scalar(
        select(func.count()).select_from(JobModel)
    )

    assert row_count == 0

    saved_job = save_job(
        database_session,
        job,
    )

    assert saved_job.id is not None