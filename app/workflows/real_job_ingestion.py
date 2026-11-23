"""Import real jobs while keeping an auditable summary of partial progress."""

from collections.abc import Callable
from datetime import datetime, timezone
import logging

from sqlalchemy.orm import Session

from app.crawlers.contracts import CrawlBatch
from app.database.ingestion_models import IngestionRunModel
from app.database.repository import upsert_job
from app.services.cleaner import clean_job


logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """SQLite stores UTC without an offset; presentation adds the timezone."""

    return datetime.now(timezone.utc).replace(tzinfo=None)


def import_job_batch(
    session: Session,
    *,
    source: str,
    fetch: Callable[[], CrawlBatch],
) -> IngestionRunModel:
    """Record a run and persist each valid item, never inferring closures.

    A source exception is a failed run, not an empty successful snapshot.
    Each upsert commits independently so a later bad item cannot erase earlier
    successes. Counts describe input observations; job_ids are unique.
    """

    run = IngestionRunModel(source=source, started_at=utc_now(), status="running")
    session.add(run)
    session.commit()
    session.refresh(run)

    counts = {"created": 0, "updated": 0, "unchanged": 0}
    job_ids: list[int] = []
    errors: list[dict[str, str | None]] = []
    warnings: list[str] = []
    complete = False
    try:
        batch = fetch()
    except Exception as exc:
        logger.warning("Job source failed: source=%s error_type=%s", source, type(exc).__name__)
        errors.append({"item_id": None, "message": "来源暂时不可用或返回格式变化，请稍后重试。"})
    else:
        complete = batch.complete
        warnings = list(batch.warnings)
        errors.extend(
            {"item_id": failure.item_id, "message": failure.message}
            for failure in batch.failures
        )
        for raw_job in batch.jobs:
            try:
                if raw_job.source.strip().casefold() != source:
                    raise ValueError("Unexpected job source")
                result = upsert_job(session, clean_job(raw_job))
            except Exception as exc:
                session.rollback()
                logger.warning("Job import failed: source=%s error_type=%s", source, type(exc).__name__)
                errors.append({
                    "item_id": raw_job.source_job_id,
                    "message": "此岗位未能保存；其他已成功保存的岗位不受影响。",
                })
            else:
                counts[result.outcome] += 1
                if result.job.id not in job_ids:
                    job_ids.append(result.job.id)

    run.created_count = counts["created"]
    run.updated_count = counts["updated"]
    run.unchanged_count = counts["unchanged"]
    run.failed_count = len(errors)
    run.errors = errors[:100]
    run.warnings = warnings[:100]
    run.job_ids = job_ids
    run.complete = complete and not errors
    run.status = (
        "failed" if errors and not job_ids
        else "partial" if not run.complete
        else "succeeded"
    )
    run.finished_at = utc_now()
    session.add(run)
    session.commit()
    session.refresh(run)
    return run
