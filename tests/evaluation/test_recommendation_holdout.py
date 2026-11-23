"""The real holdout stays traceable, complete and reproducible offline.

No minimum improvement is imposed: a disappointing comparison is a valid result.
"""

from collections import Counter
import json
from pathlib import Path
import socket

from evals.recommendation_dataset import digest, load_dataset
from evals.recommendation_comparison import baseline_application, run_version
from evals.recommendation_runner import render_markdown
from tests.evaluation.recruitment_corpus import REQUIRES_RECORDED_CORPUS


DATASET = Path(__file__).resolve().parents[2] / "evals/cases/recommendation_quality"
SOURCE = Path(__file__).resolve().parents[2] / "data/real_jobs/stage19"

pytestmark = REQUIRES_RECORDED_CORPUS


def test_real_source_coverage_and_saved_original_fingerprints():
    with baseline_application() as archived_root:
        dataset = load_dataset(DATASET, algorithm_root=archived_root)
    assert len(dataset.primary) >= 30
    assert len({j.company for j in dataset.primary.values()}) >= 3
    counts = Counter(r.metadata["collection_direction"] for r in dataset.records)
    assert all(counts[direction] >= 8 for direction in ("ai_application", "backend", "computer_vision"))
    assert len(dataset.profiles) >= 6
    assert len(dataset.gold) == len(dataset.profiles) * len(dataset.primary)
    manifest = json.loads((DATASET / "source_manifest.json").read_text(encoding="utf-8"))
    assert digest(SOURCE / "jobs.json") == manifest["source_file_sha256"]
    source_rows = {row["key"]: row for row in json.loads((SOURCE / "jobs.json").read_text(encoding="utf-8"))}
    for row in dataset.records:
        assert row.job.description == source_rows[row.job_key]["description"]
        assert row.job.status == "unknown"
        evidence = row.metadata["source_evidence"]
        raw_path = (SOURCE / evidence["raw_record_path"]).resolve()
        assert raw_path.is_relative_to(SOURCE.resolve())
        assert digest(raw_path) == evidence["raw_record_sha256"]


def test_real_comparison_is_offline_deterministic_and_does_not_require_improvement(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("A frozen comparison must not connect to the network")
    monkeypatch.setattr(socket, "create_connection", no_network)
    with baseline_application() as archived_root:
        dataset = load_dataset(DATASET, algorithm_root=archived_root)
        first, repeated = run_version(DATASET, archived_root), run_version(DATASET, archived_root)
    assert first == repeated
    preserved = json.loads((DATASET.parents[2] / "docs/evaluations/stage19-results.json").read_text(encoding="utf-8"))
    assert first["summary"] == preserved["summary"]
    assert first["profiles"] == preserved["profiles"]
    assert first["corpus"]["judged_pairs"] == len(dataset.gold)
    for system in ("baseline", "current"):
        assert first["summary"][system]["display_slots"] == 5 * len(dataset.profiles)
        assert 0 <= first["summary"][system]["precision_at_k_macro"] <= 1
    for profile in first["profiles"]:
        assert profile["production_counts"]["evaluated"] == len(dataset.primary)
        assert len(profile["current_diagnostics"]) == len(dataset.primary)
    markdown = render_markdown(first)
    for profile in first["profiles"]:
        for key in profile["systems"]["current"]["metrics"]["missed_useful_keys"]:
            decision = profile["current_diagnostics"][key]
            if decision["disposition"] == "direction_mismatch":
                assert "系统按方向排除：" + decision["direction_fit"]["reason"] in markdown
