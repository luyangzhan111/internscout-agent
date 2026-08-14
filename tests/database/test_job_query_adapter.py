from datetime import date, datetime
from types import SimpleNamespace
from typing import Any, cast

from sqlalchemy.orm import Session

from app.database import job_query_adapter
from app.database.job_query_adapter import (
    RepositoryJobQueryAdapter,
)
from app.schemas.job_response import JobRead


def make_database_job(
    *,
    job_id: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=job_id,
        title="AI 应用开发实习生",
        company="示例科技",
        city="深圳",
        salary="200-300/天",
        description="参与 AI Agent 应用开发。",
        skills=[
            "python",
            "fastapi",
        ],
        source="mock",
        source_url=(
            "https://example.com/jobs/1"
        ),
        published_at=date(
            2026,
            8,
            1,
        ),
        created_at=datetime(
            2026,
            8,
            1,
            10,
            30,
            0,
        ),
    )


def test_repository_job_query_adapter_forwards_search_and_converts_jobs(
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    session = cast(
        Session,
        object(),
    )

    def fake_query_jobs(
        received_session: Session,
        **kwargs: Any,
    ) -> tuple[list[SimpleNamespace], int]:
        captured["session"] = received_session
        captured.update(
            kwargs
        )

        return [
            make_database_job()
        ], 1

    monkeypatch.setattr(
        job_query_adapter,
        "repository_query_jobs",
        fake_query_jobs,
    )

    adapter = RepositoryJobQueryAdapter(
        session
    )

    jobs, total = adapter.search_jobs(
        city="深圳",
        company="示例科技",
        skill="python",
        page=2,
        page_size=5,
    )

    assert captured == {
        "session": session,
        "city": "深圳",
        "company": "示例科技",
        "skill": "python",
        "page": 2,
        "page_size": 5,
    }

    assert total == 1
    assert len(jobs) == 1
    assert isinstance(
        jobs[0],
        JobRead,
    )
    assert jobs[0].id == 1
    assert jobs[0].city == "深圳"


def test_repository_job_query_adapter_returns_job_detail(
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    session = cast(
        Session,
        object(),
    )

    def fake_get_job_by_id(
        received_session: Session,
        job_id: int,
    ) -> SimpleNamespace:
        captured["session"] = received_session
        captured["job_id"] = job_id

        return make_database_job(
            job_id=3
        )

    monkeypatch.setattr(
        job_query_adapter,
        "repository_get_job_by_id",
        fake_get_job_by_id,
    )

    adapter = RepositoryJobQueryAdapter(
        session
    )

    job = adapter.get_job_by_id(
        3
    )

    assert captured == {
        "session": session,
        "job_id": 3,
    }

    assert job is not None
    assert isinstance(
        job,
        JobRead,
    )
    assert job.id == 3
    assert (
        job.title
        == "AI 应用开发实习生"
    )


def test_repository_job_query_adapter_returns_none_when_job_missing(
    monkeypatch: Any,
) -> None:
    session = cast(
        Session,
        object(),
    )

    def fake_get_job_by_id(
        received_session: Session,
        job_id: int,
    ) -> None:
        return None

    monkeypatch.setattr(
        job_query_adapter,
        "repository_get_job_by_id",
        fake_get_job_by_id,
    )

    adapter = RepositoryJobQueryAdapter(
        session
    )

    assert (
        adapter.get_job_by_id(
            999999
        )
        is None
    )