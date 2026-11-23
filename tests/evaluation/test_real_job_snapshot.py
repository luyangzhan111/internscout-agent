"""Snapshot preparation cannot silently mutate labels or overwrite local jobs."""

from hashlib import sha256
import json
from pathlib import Path
import sqlite3

import pytest

from app.database import create_database_engine, create_session_factory, init_database
from app.database.repository import upsert_job
from app.schemas.ingestion import ManualJobInput
import evals.real_job_snapshot as snapshot_module
from evals.real_job_snapshot import freeze, import_snapshot, prepare
from evals.recommendation_dataset import ALGORITHM_FILES, ROOT, digest, load_dataset


def source_row(**overrides):
    row = {"key": "source-1", "title": "Python 后端实习生", "company": "官网公司", "city": "北京市",
           "description": "岗位职责：负责 Python 后端服务。\n任职要求：熟悉 Python。",
           "source_url": "https://careers.company.test/jobs/1", "source_job_id": "1", "status": "unknown",
           "observed_at": "2026-11-18T10:00:00+08:00", "direction_bucket": "backend",
           "source_evidence": {"method": "official detail", "url": "https://careers.company.test/jobs/1"}}
    row.update(overrides)
    return row


def raw_file(tmp_path, rows):
    path = tmp_path / "collected.json"
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return path


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def tiny_frozen_dataset(tmp_path, extra_evidence=None):
    directory = tmp_path / "dataset"
    prepare(raw_file(tmp_path, [source_row()]), directory)
    write_json(directory / "profiles.json", {"schema_version": 1, "profiles": [{
        "profile_id": "test", "label": "虚构测试档案", "candidate": {"skills": ["Python"],
        "target_directions": ["backend"], "conditions": {"acceptable_cities": []}}}]})
    dimensions = {dim: "unknown" for dim in ("graduation_year", "degree", "experience", "city", "internship_duration")}
    dimensions["city"] = "met"
    gold = {"profile_id": "test", "job_key": "source-1", "direction": "aligned", "eligibility": dimensions,
            "overall": "unknown", "relevance": 3, "hard_blocks": [], "reason": "原文明示 Python 后端开发；其他条件未说明。",
            "evidence": [{"field": "description", "text": "负责 Python 后端服务"}]}
    (directory / "gold.jsonl").write_text(json.dumps(gold, ensure_ascii=False) + "\n", encoding="utf-8")
    write_json(directory / "algorithm_freeze.json", {"files": {
        name: digest(ROOT / name) for name in ALGORITHM_FILES}})
    (directory / "annotation-guide.md").write_text("Synthetic fixture only", encoding="utf-8")
    if extra_evidence:
        write_json(directory / extra_evidence, {"sampling_fixed_before_ranking": True})
    freeze(directory)
    return directory


def test_prepare_preserves_exact_description_and_is_repeatable(tmp_path):
    source = raw_file(tmp_path, [source_row()])
    directory = tmp_path / "dataset"
    first = prepare(source, directory)
    second = prepare(source, directory)
    assert first == second
    row = json.loads((directory / "jobs.jsonl").read_text(encoding="utf-8"))
    assert row["job"]["city"] == "北京"
    assert row["job"]["description"] == source_row()["description"]
    assert row["job"]["skills"] == []  # No gold skills inferred by production extraction.
    assert row["metadata"]["collection_direction"] == "backend"
    assert row["job"]["status"] == "unknown"
    payload = json.loads((directory / "manual-import.json").read_text(encoding="utf-8"))["jobs"][0]
    assert payload == {name: row["job"][name] for name in ManualJobInput.model_fields}


def test_prepare_rejects_same_import_url_even_if_titles_differ(tmp_path):
    rows = [source_row(), source_row(key="other", title="另一个职位名")]
    with pytest.raises(ValueError, match="ingestion identity"):
        prepare(raw_file(tmp_path, rows), tmp_path / "dataset")


@pytest.mark.parametrize("overrides", [
    {"source_url": "https://example.com/jobs/1"}, {"observed_at": "2026-11-18T10:00:00"},
    {"source_evidence": None},
])
def test_prepare_rejects_untraceable_or_sample_sources(tmp_path, overrides):
    with pytest.raises(ValueError):
        prepare(raw_file(tmp_path, [source_row(**overrides)]), tmp_path / "dataset")


def test_prepared_input_cannot_be_replaced_silently(tmp_path):
    source = raw_file(tmp_path, [source_row()])
    directory = tmp_path / "dataset"
    prepare(source, directory)
    original = (directory / "jobs.jsonl").read_bytes()
    raw_file(tmp_path, [source_row(description="已改变的正文")])
    with pytest.raises(ValueError, match="new version"):
        prepare(source, directory)
    assert (directory / "jobs.jsonl").read_bytes() == original


def test_freeze_records_raw_byte_hash_and_rejects_refreeze(tmp_path):
    directory = tiny_frozen_dataset(tmp_path)
    manifest = json.loads((directory / "dataset_freeze.json").read_text(encoding="utf-8"))
    assert manifest["files"]["gold.jsonl"] == sha256((directory / "gold.jsonl").read_bytes()).hexdigest()
    assert manifest["source_hosts"] == ["careers.company.test"]
    (directory / "gold.jsonl").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="new version"):
        freeze(directory)


@pytest.mark.parametrize("name", ["source-capture-audit.json", "source-supplement-declaration.json",
                                  "annotation-review.json", "annotation-peer-review.json", "degree_only_algorithm_freeze.json"])
def test_source_capture_and_pre_ranking_supplement_evidence_are_frozen(tmp_path, name):
    directory = tiny_frozen_dataset(tmp_path, extra_evidence=name)
    dataset = load_dataset(directory)
    assert dataset.fingerprints["data_files"][name] == digest(directory / name)
    write_json(directory / name, {"sampling_fixed_before_ranking": False})
    with pytest.raises(ValueError, match="fingerprint|SHA|hash",):
        load_dataset(directory)


def test_import_preview_backup_and_repeatability(tmp_path):
    directory = tiny_frozen_dataset(tmp_path)
    database = tmp_path / "personal.db"
    engine = create_database_engine(f"sqlite:///{database.as_posix()}")
    init_database(engine)
    engine.dispose()
    preview = import_snapshot(directory, database)
    assert preview["first"]["created"] == 1
    assert preview["repeated"]["unchanged"] == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute("select count(*) from jobs").fetchone()[0] == 0
        assert connection.execute("select count(*) from ingestion_runs").fetchone()[0] == 0
    applied = import_snapshot(directory, database, apply=True)
    assert applied["actual"]["created"] == 1
    with sqlite3.connect(applied["backup"]) as connection:
        assert connection.execute("select count(*) from jobs").fetchone()[0] == 0
    repeated = import_snapshot(directory, database, apply=True)
    assert repeated["actual"]["created"] == 0
    assert repeated["actual"]["unchanged"] == 1
    assert repeated["actual"]["job_ids"] == applied["actual"]["job_ids"]


def make_existing_database(tmp_path, **overrides):
    database = tmp_path / "personal.db"
    engine = create_database_engine(f"sqlite:///{database.as_posix()}")
    init_database(engine)
    values = {"key": "old", "source_url": "https://careers.company.test/jobs/old", "description": "原有岗位正文", **overrides}
    row = source_row(**values)
    item = ManualJobInput.model_validate({name: row[name] for name in ManualJobInput.model_fields if name in row})
    with create_session_factory(engine)() as session:
        upsert_job(session, item.to_job())
    engine.dispose()
    return database


def test_import_preserves_existing_ids_and_every_nonbatch_field(tmp_path):
    directory = tiny_frozen_dataset(tmp_path)
    database = make_existing_database(tmp_path)
    original = snapshot_module._job_rows(database)
    result = import_snapshot(directory, database, apply=True)
    assert result["preserved_nonbatch_existing_jobs"] == 1
    assert result["actual"]["created"] == 1
    assert result["actual"]["total_jobs"] == 2
    assert snapshot_module._job_rows(database)[1] == original[1]


def test_conflicting_old_job_is_rejected_in_preview_before_real_write(tmp_path):
    directory = tiny_frozen_dataset(tmp_path)
    # The frozen batch has this URL with a different description.
    database = make_existing_database(tmp_path, source_url=source_row()["source_url"])
    before = snapshot_module._database_digest(database)
    with pytest.raises(ValueError, match="would update existing jobs"):
        import_snapshot(directory, database, apply=True)
    assert snapshot_module._database_digest(database) == before
    assert not list(tmp_path.glob("*.pre-stage19-*.bak"))


def test_live_change_after_preview_requires_new_preview(tmp_path, monkeypatch):
    directory = tiny_frozen_dataset(tmp_path)
    database = make_existing_database(tmp_path)
    original_import = snapshot_module._run_import
    calls = 0
    def simulate_another_writer(path, jobs):
        nonlocal calls
        result = original_import(path, jobs)
        calls += 1
        if calls == 2:
            with sqlite3.connect(database) as connection:
                connection.execute("UPDATE jobs SET description='外部合法修改' WHERE id=1")
        return result
    monkeypatch.setattr(snapshot_module, "_run_import", simulate_another_writer)
    with pytest.raises(ValueError, match="changed during preview"):
        import_snapshot(directory, database, apply=True)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
        assert connection.execute("SELECT description FROM jobs WHERE id=1").fetchone()[0] == "外部合法修改"
