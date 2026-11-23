"""Small, repeatable SQLite upgrade for the job lifecycle schema.

Legacy rows keep their IDs and creation dates. Ambiguous duplicate identities
are retained as explicit legacy-conflict rows instead of silently deleting data.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy import Engine, inspect

from app.database.models import Base
from app.services.deduplicator import build_job_identity


_LIFECYCLE_COLUMNS = {
    "source_job_id": "VARCHAR(200)",
    "status": "VARCHAR(20) NOT NULL DEFAULT 'unknown'",
    "updated_at": "DATETIME",
    "last_seen_at": "DATETIME",
    "last_checked_at": "DATETIME",
}


def _backup_sqlite_database(engine: Engine) -> Path | None:
    # SQLite resolves both ordinary paths and file: URIs for us. An empty main
    # path means an in-memory database, for which there is no file to back up.
    with engine.connect() as connection:
        database = next(
            (row[2] for row in connection.exec_driver_sql("PRAGMA database_list")
             if row[1] == "main"), ""
        )
    if not database:
        return None
    original = Path(database).resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = original.with_name(
        f"{original.name}.pre-lifecycle-{stamp}-{uuid4().hex[:8]}.bak"
    )
    with sqlite3.connect(original.as_uri() + "?mode=ro", uri=True) as source:
        with sqlite3.connect(backup) as destination:
            source.backup(destination)
    return backup


def _legacy_source_id(source: str, source_url: str) -> str | None:
    if source != "oppo":
        return None
    try:
        parts = urlsplit(source_url)
        if (
            parts.scheme.lower() != "https"
            or parts.hostname != "career.oppo.com"
            or parts.username is not None
            or parts.password is not None
            or parts.port not in {None, 443}
        ):
            return None
    except ValueError:
        return None
    match = re.fullmatch(
        r"/official/oppo/recruitment/post/([0-9]+)/?", parts.path
    )
    return match.group(1) if match else None


def migrate_database(engine: Engine) -> Path | None:
    """Upgrade existing SQLite jobs atomically, returning a new backup path.

    New databases are handled by create_all. Observation dates deliberately stay
    NULL on legacy rows: an upgrade is not evidence that a job was checked today.
    """

    inspector = inspect(engine)
    if "jobs" not in inspector.get_table_names():
        return None
    columns = {column["name"] for column in inspector.get_columns("jobs")}
    missing = set(_LIFECYCLE_COLUMNS) - columns
    if not missing:
        return None
    if engine.dialect.name != "sqlite":
        raise ValueError("Automatic legacy migration currently supports SQLite only")

    backup = _backup_sqlite_database(engine)
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            # Recheck under the writer lock: another process may have migrated.
            current_columns = {
                row[1] for row in connection.exec_driver_sql("PRAGMA table_info(jobs)")
            }
            still_missing = set(_LIFECYCLE_COLUMNS) - current_columns
            if not still_missing:
                connection.commit()
                return backup
            for name in _LIFECYCLE_COLUMNS:
                if name in still_missing:
                    connection.exec_driver_sql(
                        f"ALTER TABLE jobs ADD COLUMN {name} {_LIFECYCLE_COLUMNS[name]}"
                    )
            rows = list(connection.exec_driver_sql("SELECT * FROM jobs ORDER BY id").mappings())
            desired: list[tuple[int, str, str | None, str]] = []
            seen: set[str] = set()
            for row in rows:
                source = row["source"].strip().lower()
                source_id = row["source_job_id"] or _legacy_source_id(source, row["source_url"])
                try:
                    identity = build_job_identity(SimpleNamespace(
                        source=source,
                        source_job_id=source_id,
                        source_url=row["source_url"],
                        company=row["company"],
                        title=row["title"],
                        city=row["city"],
                    ))
                    key = json.dumps(identity, ensure_ascii=False, separators=(",", ":"))
                except ValueError:
                    # Invalid legacy URLs remain inspectable, but cannot steal
                    # a future valid source identity.
                    key = json.dumps(["legacy_invalid_url", source, row["id"]])
                if key in seen:
                    key = json.dumps(["legacy_conflict", key, row["id"]], ensure_ascii=False)
                seen.add(key)
                desired.append((row["id"], source, source_id, key))

            # Temporary keys avoid collisions with old identities during re-key.
            prefix = "migration:" + uuid4().hex + ":"
            for job_id, _, _, _ in desired:
                connection.exec_driver_sql(
                    "UPDATE jobs SET identity_key = ? WHERE id = ?",
                    (prefix + str(job_id), job_id),
                )
            for job_id, source, source_id, key in desired:
                connection.exec_driver_sql(
                    "UPDATE jobs SET identity_key = ?, source = ?, source_job_id = ? WHERE id = ?",
                    (key, source, source_id, job_id),
                )
            Base.metadata.create_all(bind=connection)
            connection.exec_driver_sql(
                "INSERT OR IGNORE INTO dataset_state (id, revision) VALUES (1, 0)"
            )
            if rows:
                connection.exec_driver_sql(
                    "UPDATE dataset_state SET revision = revision + 1 WHERE id = 1"
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return backup
