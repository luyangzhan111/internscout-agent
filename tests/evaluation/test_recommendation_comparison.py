"""Version isolation preserves the old implementation instead of relabeling it."""

import copy
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from evals.recommendation_comparison import (
    BASELINE, BASELINES, ROOT, baseline_application, compare, comparison_markdown, main, run_version,
)
from evals.recommendation_dataset import load_dataset
from tests.evaluation.recruitment_corpus import REQUIRES_RECORDED_CORPUS
from tests.evaluation.test_recommendation_quality import write_dataset


@REQUIRES_RECORDED_CORPUS
def test_archived_baseline_exactly_matches_original_stage19_manifest():
    expected = json.loads((ROOT / "evals/cases/recommendation_quality/algorithm_freeze.json").read_text(encoding="utf-8"))
    with baseline_application() as archived:
        for name, checksum in expected["files"].items():
            assert sha256((archived / name).read_bytes()).hexdigest() == checksum
        dataset = load_dataset(ROOT / "evals/cases/recommendation_quality", algorithm_root=archived)
        assert len(dataset.gold) == 180
        assert len(dataset.primary) == 30


def test_tampered_archive_is_rejected(tmp_path):
    directory = tmp_path / "archive"
    directory.mkdir()
    (directory / "manifest.json").write_bytes((BASELINE / "manifest.json").read_bytes())
    (directory / "application.zip").write_bytes((BASELINE / "application.zip").read_bytes() + b"changed")
    with pytest.raises(ValueError, match="SHA-256"):
        with baseline_application(directory):
            pytest.fail("An altered baseline was accepted")


@pytest.mark.parametrize("member", ["../escape.py", "/absolute.py", "C:/drive.py", "app\\escape.py"])
def test_unsafe_archive_paths_are_rejected_even_with_matching_outer_hash(tmp_path, member):
    directory = tmp_path / "archive"
    directory.mkdir()
    content, freeze = b"pass\n", b"{}\n"
    with ZipFile(directory / "application.zip", "w") as archive:
        archive.writestr(member, content)
        archive.writestr("algorithm_freeze.json", freeze)
    manifest = {"archive_sha256": sha256((directory / "application.zip").read_bytes()).hexdigest(),
                "source_manifest_sha256": sha256(freeze).hexdigest(),
                "files": {member: sha256(content).hexdigest()}}
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsafe|unexpected"):
        with baseline_application(directory):
            pytest.fail("An escaping path was accepted")
    assert not (ROOT / "tmp/escape.py").exists()


def test_current_version_executes_in_offline_isolated_process(tmp_path):
    directory = write_dataset(tmp_path / "data")
    report = run_version(directory, ROOT)
    assert report["corpus"]["profiles"] == 1
    assert report["corpus"]["independent_jobs"] == 3
    combined = compare(directory, previous=report, fixed=report)
    assert combined["summary"]["previous_recommender"] == combined["summary"]["fixed_recommender"]
    assert combined["qualification_safety"]["fixed"]["known_qualification_blocks"] == 1
    assert "修复前推荐" in comparison_markdown(combined)
    wrong = copy.deepcopy(report)
    wrong["profiles"][0]["systems"]["baseline"]["ranking"].reverse()
    with pytest.raises(ValueError, match="shared skill baseline"):
        compare(directory, previous=report, fixed=wrong)


def test_cli_rejects_fingerprint_root_other_than_the_imported_version(tmp_path):
    directory = write_dataset(tmp_path / "data")
    with pytest.raises(ValueError, match="imported application"):
        run_version(directory, tmp_path / "not-an-application")


@REQUIRES_RECORDED_CORPUS
def test_stage20_archive_matches_its_original_frozen_source():
    directory = ROOT / "evals/cases/recommendation_quality_stage20"
    expected = json.loads((directory / "algorithm_freeze.json").read_text(encoding="utf-8"))
    with baseline_application(BASELINES["stage20"]) as archived:
        for name, checksum in expected["files"].items():
            assert sha256((archived / name).read_bytes()).hexdigest() == checksum
        dataset = load_dataset(directory, algorithm_root=archived)
        assert len(dataset.gold) == 192


def test_selected_baseline_controls_comparison_archive_identity(tmp_path):
    report = run_version(write_dataset(tmp_path / "data"), ROOT)
    selected = compare(tmp_path, previous=report, fixed=report, baseline=BASELINES["stage20"])
    assert selected["baseline_version"] == "stage20"
    assert selected["archived_application_sha256"] == sha256((BASELINES["stage20"] / "application.zip").read_bytes()).hexdigest()
    assert "archived stage20" in selected["protocol"]
    assert "Stage 21" in comparison_markdown(selected)
    assert "方向硬排与待确认保留" in comparison_markdown(selected)


@REQUIRES_RECORDED_CORPUS
def test_selected_stage20_archive_replays_original_dataset_without_current_rules(tmp_path):
    directory = ROOT / "evals/cases/recommendation_quality_stage20"
    output, markdown = tmp_path / "replay.json", tmp_path / "replay.md"
    main(["--dataset", str(directory), "--baseline", "stage20", "--replay-archive",
          "--json", str(output), "--markdown", str(markdown)])
    actual = json.loads(output.read_text(encoding="utf-8"))
    original = json.loads((ROOT / "docs/evaluations/stage20-holdout.json").read_text(encoding="utf-8"))
    assert actual["summary"]["current"] == original["summary"]["fixed_recommender"]
    assert actual["profiles"] == original["versions"]["fixed"]["profiles"]
    assert actual["eligibility_rules_versions"] == ["stage20-rules-v1"]
