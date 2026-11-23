"""Legacy copies migrate without losing rows, IDs, or provenance."""

import json
import sqlite3

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.database import create_database_engine, get_dataset_revision, init_database, list_jobs
import app.database.migrations as migrations


def legacy_database(path):
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identity_key VARCHAR(300) NOT NULL UNIQUE,
            title VARCHAR(100) NOT NULL, company VARCHAR(100) NOT NULL,
            city VARCHAR(50) NOT NULL, salary VARCHAR(100),
            description TEXT NOT NULL, skills JSON NOT NULL,
            source VARCHAR(50) NOT NULL, source_url TEXT NOT NULL,
            published_at DATE, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        for row_id, title, source, url in [
            (7, "Backend A", " OPPO ", "https://career.oppo.com/official/oppo/recruitment/post/123?recruitType=OFFEN-RECRUITMENT"),
            (19, "Backend B", "oppo", "https://career.oppo.com/official/oppo/recruitment/post/123?recruitType=OFFEN-RECRUITMENT"),
            (23, "Untrusted", "oppo", "https://career.oppo.com.evil.example/official/oppo/recruitment/post/456"),
            (31, "Legacy import", "manual", "legacy-invalid-url"),
            (44, "Mock job", "mock", "https://example.com/demo"),
        ]:
            connection.execute("""INSERT INTO jobs
                (id, identity_key, title, company, city, description, skills, source,
                 source_url, created_at, published_at)
                VALUES (?, ?, ?, 'Example', '深圳', 'Original description', '["Python"]',
                        ?, ?, '2026-07-30 11:04:06', '2026-07-20')""",
                (row_id, json.dumps(["example", title.lower(), "深圳"]), title, source, url))


def test_migration_keeps_all_ids_dates_and_conflicts_and_runs_once(tmp_path):
    path = tmp_path / "legacy.db"
    legacy_database(path)
    engine = create_database_engine(f"sqlite:///{path.as_posix()}")
    init_database(engine)
    with Session(engine) as session:
        rows = list_jobs(session)
        assert [row.id for row in rows] == [7, 19, 23, 31, 44]
        assert len({row.identity_key for row in rows}) == 5
        assert rows[0].source == "oppo"
        assert rows[0].source_job_id == "123"
        assert json.loads(rows[0].identity_key) == ["v2", "source_id", "oppo", "123"]
        assert json.loads(rows[1].identity_key)[0] == "legacy_conflict"
        assert rows[2].source_job_id is None  # Lookalike host is not trusted.
        assert json.loads(rows[2].identity_key)[:2] == ["v2", "source_url"]
        assert json.loads(rows[3].identity_key)[0] == "legacy_invalid_url"
        assert json.loads(rows[4].identity_key) == ["example", "mock job", "深圳"]
        assert all(str(row.created_at) == "2026-07-30 11:04:06" for row in rows)
        assert all(row.status == "unknown" for row in rows)
        assert all(row.last_seen_at is None and row.last_checked_at is None for row in rows)
        assert all(row.updated_at is None for row in rows)
        assert get_dataset_revision(session) == 1
        original_keys = [row.identity_key for row in rows]
    backups = list(tmp_path.glob("legacy.db.pre-lifecycle-*.bak"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as backup:
        assert backup.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 5
        assert "source_job_id" not in {row[1] for row in backup.execute("PRAGMA table_info(jobs)")}
    init_database(engine)
    with Session(engine) as session:
        assert [row.identity_key for row in list_jobs(session)] == original_keys
        assert get_dataset_revision(session) == 1
    assert list(tmp_path.glob("legacy.db.pre-lifecycle-*.bak")) == backups
    engine.dispose()


def test_failed_migration_rolls_back_columns_and_rows(tmp_path, monkeypatch):
    path = tmp_path / "failure.db"
    legacy_database(path)
    engine = create_database_engine(f"sqlite:///{path.as_posix()}")
    original_columns = {column["name"] for column in inspect(engine).get_columns("jobs")}
    def fail_identity(_):
        raise RuntimeError("simulated migration failure")
    monkeypatch.setattr(migrations, "build_job_identity", fail_identity)
    with pytest.raises(RuntimeError, match="simulated"):
        init_database(engine)
    assert {column["name"] for column in inspect(engine).get_columns("jobs")} == original_columns
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 5
        assert connection.execute("SELECT source FROM jobs WHERE id = 7").fetchone()[0] == " OPPO "
    assert len(list(tmp_path.glob("failure.db.pre-lifecycle-*.bak"))) == 1
    engine.dispose()
