"""User-visible identity, refresh, revision, and concurrency behavior."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.database.repository as repository
from app.database import (
    JobModel, create_database_engine, get_dataset_revision, init_database,
    list_jobs, query_jobs, upsert_job,
)
from app.schemas.job import JobCreate


def job(**changes) -> JobCreate:
    values = dict(title="Backend intern", company="Example", city="深圳",
                  description="Python APIs", skills=["Python"], source="oppo",
                  source_job_id="A", source_url="https://example.com/jobs/A", status="active")
    values.update(changes)
    return JobCreate(**values)


@pytest.fixture
def engine(tmp_path):
    value = create_database_engine(f"sqlite:///{(tmp_path / 'lifecycle.db').as_posix()}")
    init_database(value)
    yield value
    value.dispose()


def test_refresh_updates_content_but_unchanged_only_refreshes_observation(engine, monkeypatch):
    start = datetime(2026, 11, 12, 1, tzinfo=timezone.utc)
    dates = iter([start, start + timedelta(hours=1), start + timedelta(hours=2)])
    class Clock:
        @staticmethod
        def now(tz):
            return next(dates)
    monkeypatch.setattr(repository, "datetime", Clock)
    with Session(engine) as session:
        first = upsert_job(session, job())
        job_id, created_at, updated_at = first.job.id, first.job.created_at, first.job.updated_at
        assert first.outcome == "created"
        assert get_dataset_revision(session) == 1
        same = upsert_job(session, job())
        assert same.outcome == "unchanged"
        assert same.job.updated_at == updated_at
        assert same.job.last_seen_at == (start + timedelta(hours=1)).replace(tzinfo=None)
        assert same.job.last_checked_at == same.job.last_seen_at
        assert get_dataset_revision(session) == 1
        changed = upsert_job(session, job(description="Python and SQL", status="closed"))
        assert changed.outcome == "updated"
        assert changed.job.id == job_id
        assert changed.job.created_at == created_at
        assert changed.job.description == "Python and SQL"
        assert changed.job.status == "closed"
        assert changed.job.updated_at == (start + timedelta(hours=2)).replace(tzinfo=None)
        assert get_dataset_revision(session) == 2


def test_same_title_source_ids_remain_distinct_and_closed_filter_is_explicit(engine):
    with Session(engine) as session:
        first = upsert_job(session, job())
        upsert_job(session, job(source_job_id="B", status="closed"))
        upsert_job(session, job(source="manual", status="unknown"))
        assert len(list_jobs(session)) == 3
        items, total = query_jobs(session, source=" OPPO ", include_closed=False)
        assert total == 1
        assert items[0].id == first.job.id
        assert query_jobs(session, status="closed")[1] == 1
        assert query_jobs(session)[1] == 3  # Existing callers retain closed rows.
        renamed = upsert_job(session, job(title="Platform intern"))
        assert renamed.job.id == first.job.id
        assert len(list_jobs(session)) == 3


def test_manual_same_id_different_sites_and_later_id_metadata(engine):
    with Session(engine) as session:
        first = upsert_job(session, job(source="manual", source_job_id=None,
                                      source_url="https://one.example/jobs/123"))
        original_id = first.job.id
        enriched = upsert_job(session, job(source="manual", source_job_id="123",
                                         source_url="https://one.example/jobs/123"))
        other = upsert_job(session, job(source="manual", source_job_id="123",
                                      source_url="https://two.example/jobs/123"))
        assert enriched.job.id == original_id
        assert enriched.outcome == "updated"
        assert enriched.job.source_job_id == "123"
        assert other.job.id != original_id
        assert other.outcome == "created"
        assert len(list_jobs(session)) == 2


def test_failed_job_write_rolls_back_dataset_revision(engine, monkeypatch):
    with Session(engine) as session:
        original = session.commit
        def fail_commit():
            raise IntegrityError("write", {}, RuntimeError("simulated failure"))
        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(IntegrityError):
            upsert_job(session, job())
        monkeypatch.setattr(session, "commit", original)
        assert list_jobs(session) == []
        assert get_dataset_revision(session) == 0


def test_two_sessions_observe_the_same_dataset_revision(engine):
    with Session(engine) as reader, Session(engine) as writer:
        assert get_dataset_revision(reader) == 0
        upsert_job(writer, job())
        reader.rollback()  # A new read transaction observes the committed version.
        assert get_dataset_revision(reader) == 1


def test_unique_insert_race_reloads_and_updates_winning_row(engine, monkeypatch):
    with Session(engine) as session:
        first = upsert_job(session, job())
        original_id = first.job.id
        original_lookup = repository.get_job_by_identity_key
        lookups = 0
        def stale_first_lookup(session, identity_key):
            nonlocal lookups
            lookups += 1
            return None if lookups == 1 else original_lookup(session, identity_key)
        monkeypatch.setattr(repository, "get_job_by_identity_key", stale_first_lookup)
        result = upsert_job(session, job(description="Updated after a concurrent insert"))
        assert result.outcome == "updated"
        assert result.job.id == original_id
        assert result.job.description == "Updated after a concurrent insert"
        assert len(list_jobs(session)) == 1
        assert get_dataset_revision(session) == 2  # Failed insert did not increment.


def test_concurrent_same_identity_imports_create_one_row_and_one_revision(engine):
    def write(_):
        with Session(engine) as session:
            result = upsert_job(session, job())
            return result.job.id, result.outcome
    with ThreadPoolExecutor(max_workers=4) as workers:
        results = list(workers.map(write, range(8)))
    assert len({row_id for row_id, _ in results}) == 1
    assert [outcome for _, outcome in results].count("created") == 1
    with Session(engine) as session:
        assert len(list(session.scalars(select(JobModel)))) == 1
        assert get_dataset_revision(session) == 1
