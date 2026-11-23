"""Prepare, freeze and safely import a small, auditable real-job corpus.

Preparation and evaluation are offline. Import defaults to an isolated preview;
--apply additionally writes the explicitly named local SQLite after a backup.
"""

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from app.crawlers.contracts import CrawlBatch
from app.database import create_database_engine, create_session_factory, init_database
from app.database.repository import build_identity_key, list_jobs
from app.recommendations.identity import group_jobs, is_sample_record
from app.schemas.ingestion import ManualJobInput
from app.schemas.job_response import JobRead
from app.services.cleaner import clean_job
from app.workflows.real_job_ingestion import import_job_batch


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write_once(path: Path, text: str) -> None:
    """Refuse to silently replace a prepared/frozen input."""
    if path.exists():
        if path.read_bytes() != text.encode("utf-8"):
            raise ValueError(f"Existing input differs; use a new version directory: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def prepare(source: Path, directory: Path) -> dict:
    raw = json.loads(source.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("The source must be a nonempty array of collected jobs.")
    keys, identities, records, payload, sources = set(), set(), [], [], []
    for index, item in enumerate(sorted(raw, key=lambda row: row["key"]), 1):
        key = item["key"]
        if not isinstance(key, str) or not key.strip() or key in keys:
            raise ValueError("Collected source keys must be unique and nonempty.")
        keys.add(key)
        manual = ManualJobInput.model_validate({
            name: item[name] for name in ManualJobInput.model_fields if name in item
        })
        observed = datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError(f"Observation time must include a timezone: {key}")
        evidence = item.get("source_evidence")
        if not evidence:
            raise ValueError(f"Missing collection evidence: {key}")
        normalized = clean_job(manual.to_job())
        identity = build_identity_key(normalized)
        if identity in identities:
            raise ValueError(f"Collected jobs share an ingestion identity: {key}")
        identities.add(identity)
        snapshot = JobRead(
            id=index, **normalized.model_dump(), created_at=observed,
            updated_at=observed, last_seen_at=observed, last_checked_at=observed,
        )
        if is_sample_record(snapshot):
            raise ValueError(f"Sample data cannot be a new real source: {key}")
        content_hash = sha256(json.dumps(normalized.model_dump(mode="json"), ensure_ascii=False,
                                          sort_keys=True).encode("utf-8")).hexdigest()
        metadata = {"collection_direction": item.get("direction_bucket"),
                    "observed_at": observed.isoformat(), "content_sha256": content_hash,
                    "source_evidence": evidence}
        records.append({"job_key": key, "job": snapshot.model_dump(mode="json"), "metadata": metadata})
        payload.append(ManualJobInput.model_validate({
            name: getattr(normalized, name) for name in ManualJobInput.model_fields
        }).model_dump(mode="json"))
        sources.append({"job_key": key, "source_url": snapshot.source_url, "company": snapshot.company,
                        "title": snapshot.title, "status": snapshot.status, **metadata})
    if len(group_jobs([JobRead.model_validate(r["job"]) for r in records])) != len(records):
        raise ValueError("The collected pool contains duplicate source jobs; resolve before labelling.")
    directory.mkdir(parents=True, exist_ok=True)
    _write_once(directory / "jobs.jsonl", "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records))
    _write_once(directory / "manual-import.json", _json_text({"jobs": payload}))
    _write_once(directory / "source_manifest.json", _json_text({
        "source_file_sha256": file_hash(source), "records": sources,
        "note": "Observation is collection time, not a guarantee of a live application opening.",
    }))
    provenance = source.with_name("provenance.json")
    if provenance.exists():
        _write_once(directory / "source_provenance.json", _json_text(
            json.loads(provenance.read_text(encoding="utf-8-sig"))))
    return {"jobs": len(records), "companies": dict(Counter(r["job"]["company"] for r in records)),
            "collection_directions": dict(Counter(r["metadata"]["collection_direction"] for r in records)),
            "jobs_sha256": file_hash(directory / "jobs.jsonl")}


def freeze(directory: Path) -> dict:
    names = ["jobs.jsonl", "profiles.json", "gold.jsonl", "annotation-guide.md",
             "algorithm_freeze.json", "source_manifest.json", "manual-import.json"]
    for optional in ("source_provenance.json", "annotation-review.md", "annotation-review.json", "annotation-facts.json", "labeling-notes.md",
                     "annotation-peer-review.md", "annotation-peer-review.json", "annotation-peer-pre-read.json",
                     "annotation-peer-review-checks.json", "build_gold.py",
                     "source-review.md", "source-ownership.json", "source-capture-audit.json",
                     "source-supplement-declaration.json", "previous_algorithm_freeze.json",
                     "degree_only_algorithm_freeze.json", "source-sampling-manifest.json", "source-input-ready.json",
                     "source-discovery-declaration.json", "source-route-correction.json",
                     "source-combined-field-declaration.json", "source-role-review.json",
                     "source-import-normalization-amendment.json", "source-production-cleaning-audit.json",
                     "source-raw-capture-inventory.json", "source-discovery-manifest.json"):
        if (directory / optional).exists():
            names.append(optional)
    rows = [json.loads(line) for line in (directory / "jobs.jsonl").read_text(encoding="utf-8").splitlines() if line]
    manifest = {"schema_version": 1, "files": {name: file_hash(directory / name) for name in names},
                "source_hosts": sorted({urlsplit(row["job"]["source_url"]).hostname for row in rows}),
                "label_independence": "New-source holdout; AI-assisted blind labels, project-internal review; no independent human validation."}
    _write_once(directory / "dataset_freeze.json", _json_text(manifest))
    return manifest


def _copy_sqlite(source: Path, destination: Path) -> None:
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(destination)) as dst:
            src.backup(dst)


def _database_digest(database: Path) -> str:
    """Hash a consistent logical read, including import history and revision."""
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("BEGIN")
        schema = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        contents = []
        for name, sql in schema:
            quoted = '"' + name.replace('"', '""') + '"'
            rows = [json.dumps(list(row), ensure_ascii=False, default=str)
                    for row in connection.execute(f"SELECT * FROM {quoted}")]
            contents.append([name, sql, sorted(rows)])
    return sha256(json.dumps(contents, ensure_ascii=False).encode("utf-8")).hexdigest()


def _job_rows(database: Path) -> dict[int, dict]:
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        return {row["id"]: dict(row) for row in connection.execute("SELECT * FROM jobs ORDER BY id")}


def _assert_preserved(before: dict[int, dict], after: dict[int, dict]) -> list[int]:
    """Allow only internal legacy-key repair, never replacing old job content."""
    repaired = []
    for job_id, original in before.items():
        current = after.get(job_id)
        if current is None or {k: v for k, v in original.items() if k != "identity_key"} != {
            k: v for k, v in current.items() if k != "identity_key"
        }:
            raise ValueError(f"Snapshot import would change an existing job: ID {job_id}")
        if original.get("identity_key") != current.get("identity_key"):
            repaired.append(job_id)
    return repaired


def _run_import(database: Path, jobs: list[ManualJobInput]) -> dict:
    engine = create_database_engine(f"sqlite:///{database.resolve().as_posix()}")
    init_database(engine)
    try:
        with create_session_factory(engine)() as session:
            run = import_job_batch(session, source="manual", fetch=lambda: CrawlBatch(
                jobs=[item.to_job() for item in jobs], failures=[], complete=True))
            result = {"run_id": run.id, "status": run.status, "created": run.created_count,
                      "updated": run.updated_count, "unchanged": run.unchanged_count,
                      "failed": run.failed_count, "job_ids": list(run.job_ids),
                      "total_jobs": len(list_jobs(session))}
            if run.failed_count or not run.complete:
                raise RuntimeError(f"Incomplete snapshot import: {result}")
            return result
    finally:
        engine.dispose()


def import_snapshot(directory: Path, database: Path, *, apply: bool = False) -> dict:
    from evals.recommendation_dataset import load_dataset
    dataset = load_dataset(directory)
    frozen_records = {record.job_key: record.job for record in dataset.records}
    if len(frozen_records) != len(dataset.primary):
        raise ValueError("Import requires a unique nonsample frozen source pool.")
    payload = json.loads((directory / "manual-import.json").read_text(encoding="utf-8"))
    jobs = [ManualJobInput.model_validate(item) for item in payload["jobs"]]
    normalized = {item.source_url.__str__(): clean_job(item.to_job()) for item in jobs}
    if len(normalized) != len(jobs):
        raise ValueError("Import payload repeats a URL identity.")
    if len({build_identity_key(item) for item in normalized.values()}) != len(jobs):
        raise ValueError("Import payload repeats a canonical ingestion identity.")
    fields = tuple(ManualJobInput.model_fields)
    for job in frozen_records.values():
        expected = normalized.get(job.source_url)
        if expected is None or any(getattr(expected, field) != getattr(job, field) for field in fields):
            raise ValueError("Import payload does not match the frozen evaluation snapshot.")
    if len(jobs) != len(frozen_records):
        raise ValueError("Import payload must have exactly the frozen source records.")
    database = database.resolve()
    if not database.is_file():
        raise ValueError("Explicit database must already exist; create an isolated database first.")
    with TemporaryDirectory(prefix="internscout-import-") as temporary:
        preview = Path(temporary) / "preview.db"
        _copy_sqlite(database, preview)
        base_digest = _database_digest(preview)
        original_rows = _job_rows(preview)
        first = _run_import(preview, jobs)
        if first["updated"]:
            raise ValueError("The frozen batch would update existing jobs; use the normal manual-update flow instead.")
        repeated = _run_import(preview, jobs)
        if repeated["created"] or repeated["updated"] or repeated["job_ids"] != first["job_ids"]:
            raise ValueError("Repeated snapshot import changed IDs or content in the isolated preview.")
        # Reobserving identical batch records changes their observation dates;
        # every old row outside that same batch must remain unchanged.
        imported_ids = set(first["job_ids"])
        protected = {key: value for key, value in original_rows.items() if key not in imported_ids}
        repaired = _assert_preserved(protected, _job_rows(preview))
    result = {"mode": "preview", "first": first, "repeated": repeated,
              "preserved_nonbatch_existing_jobs": len(protected), "legacy_key_repaired_ids": repaired,
              "preview_base_sha256": base_digest}
    if apply:
        if _database_digest(database) != base_digest:
            raise ValueError("The database changed during preview; rerun before applying.")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = database.with_name(f"{database.name}.pre-stage19-{stamp}.bak")
        _copy_sqlite(database, backup)
        if _database_digest(backup) != base_digest:
            raise ValueError(f"The database changed before backup; no import applied. Backup: {backup}")
        actual = _run_import(database, jobs)
        if actual["updated"] or any(actual[key] != first[key] for key in ("created", "updated", "unchanged", "job_ids", "total_jobs")):
            raise RuntimeError(f"Live import diverged from preview; inspect before continuing. Backup: {backup}")
        _assert_preserved(protected, _job_rows(database))
        result.update(mode="applied", backup=str(backup), actual=actual)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_command = commands.add_parser("prepare")
    prepare_command.add_argument("--source", type=Path, required=True)
    for name in ("freeze", "import"):
        command = commands.add_parser(name)
        if name == "import":
            command.add_argument("--database", type=Path, required=True)
            command.add_argument("--apply", action="store_true")
    for command in (prepare_command, *[commands.choices[name] for name in ("freeze", "import")]):
        command.add_argument("--dataset", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.source, args.dataset)
    elif args.command == "freeze":
        result = freeze(args.dataset)
    else:
        result = import_snapshot(args.dataset, args.database, apply=args.apply)
    print(_json_text(result))


if __name__ == "__main__":
    main()
