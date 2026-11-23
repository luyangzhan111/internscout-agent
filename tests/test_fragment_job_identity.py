"""Distinct SPA jobs survive import, including legacy fragment-stripped keys."""

import json

import pytest
from sqlalchemy import select

from app.database import create_database_engine, create_session_factory, init_database
from app.database.models import JobModel
from app.database.repository import build_identity_key, upsert_job
from app.schemas.job import JobCreate


def job(route):
    return JobCreate(title="后端开发", company="招聘来源", city="北京", description="熟悉 Python",
                     source="manual", source_url="https://careers.company.test/" + route)


@pytest.mark.parametrize("new_route", ["#/jobs/22", ""])
def test_new_job_does_not_overwrite_legacy_hash_route(tmp_path, new_route):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'routes.db').as_posix()}")
    init_database(engine)
    factory = create_session_factory(engine)
    first, second = job("#/jobs/11"), job(new_route)
    with factory() as session:
        saved = upsert_job(session, first).job
        first_id = saved.id
        # Represent a row written by Stage14's fragment-stripping identity.
        saved.identity_key = build_identity_key(job(""))
        session.commit()
        result = upsert_job(session, second)
        assert result.outcome == "created"
        assert result.job.id != first_id
        assert upsert_job(session, first).job.id == first_id
        assert upsert_job(session, first).outcome == "unchanged"
        assert upsert_job(session, second).outcome == "unchanged"
        assert len(session.scalars(select(JobModel)).all()) == 2
        assert session.get(JobModel, first_id).source_url == first.source_url
    engine.dispose()


def test_reimport_legacy_route_keeps_its_id(tmp_path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    init_database(engine)
    with create_session_factory(engine)() as session:
        original = job("#/jobs/11")
        row = upsert_job(session, original).job
        row_id = row.id
        row.identity_key = build_identity_key(job(""))
        session.commit()
        result = upsert_job(session, original)
        assert result.outcome == "unchanged"
        assert result.job.id == row_id
        assert result.job.identity_key == build_identity_key(original)
    engine.dispose()


def test_preexisting_collision_retains_both_rows(tmp_path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'conflict.db').as_posix()}")
    init_database(engine)
    with create_session_factory(engine)() as session:
        original = job("#/jobs/11")
        row = upsert_job(session, original).job
        row.identity_key = build_identity_key(job(""))
        session.commit()
        duplicate = JobModel(**{k: v for k, v in row.__dict__.items() if not k.startswith('_') and k != 'id'})
        duplicate.identity_key = build_identity_key(original)
        session.add(duplicate)
        session.commit()
        result = upsert_job(session, job(""))
        assert result.outcome == "created"
        rows = session.scalars(select(JobModel)).all()
        assert len(rows) == 3
        assert any(json.loads(r.identity_key)[0] == "legacy_fragment_conflict" for r in rows)
    engine.dispose()
