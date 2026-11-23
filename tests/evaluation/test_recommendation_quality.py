"""Hand-calculated metrics, fair production integration and frozen-input rejection."""

from datetime import datetime, timezone
from hashlib import sha256
import json
from math import log2
from pathlib import Path

import pytest

from app.recommendations.contracts import RecommendationCandidate
from app.schemas.job_response import JobRead
from evals.recommendation_dataset import (
    ALGORITHM_FILES, ALGORITHM_LINE_ENDINGS_POLICY, DIMENSIONS, ROOT,
    Dataset, Gold, JobRecord, Profile, _verify_files, digest, load_dataset,
)
from evals.recommendation_runner import main, render_markdown, run_dataset
from evals.recommendation_scorers import aggregate_metrics, score_ranking


def job(job_id=1, **overrides):
    data = dict(id=job_id, title="后端开发工程师", company="单元测试来源", city="北京", salary=None,
                description="任职要求：熟悉 Python。", skills=[], source="manual",
                source_url=f"https://careers.company.test/jobs/{job_id}", source_job_id=str(job_id),
                status="unknown", published_at=None, created_at=datetime(2026, 11, 18, tzinfo=timezone.utc))
    data.update(overrides)
    return JobRead(**data)


def profile(profile_id="backend"):
    return Profile(profile_id=profile_id, label="后端本科在读", candidate=RecommendationCandidate(
        skills=["Python"], target_directions=["backend"],
        conditions={"degree": "bachelor", "degree_status": "enrolled", "graduation_year": 2027,
                    "work_experience_months": 0, "acceptable_cities": [], "internship_months": 6}))


def judgement(key="job-1", *, relevance=3, direction="aligned", blocks=(), source=None):
    dimensions = {dimension: "unknown" for dimension in DIMENSIONS}
    dimensions["city"] = "met"
    dimensions.update({dimension: "not_met" for dimension in blocks})
    return Gold(profile_id="backend", job_key=key, direction=direction, eligibility=dimensions,
                overall="not_met" if blocks else "unknown", relevance=relevance,
                hard_blocks=list(blocks), reason="依据冻结岗位原文与合成条件判断。",
                evidence=[{"field": "title", "text": (source or job()).title}])


def tiny_dataset():
    # Skill-only ties prefer the unrelated/blocked lower IDs. Current production
    # is expected to retain only job-3; no fake model or reconstructed rule path.
    jobs = [job(1, title="公关经理"),
            job(2, description="任职要求：硕士及以上学历，2年以上工作经验；熟悉 Python。"),
            job(3)]
    records = [JobRecord(job_key=f"job-{j.id}", job=j) for j in jobs]
    gold = [judgement("job-1", relevance=0, direction="unrelated", source=jobs[0]),
            judgement("job-2", relevance=0, blocks=("degree", "experience"), source=jobs[1]),
            judgement("job-3", source=jobs[2])]
    return Dataset(records, {r.job_key: r.job for r in records}, [profile()],
                   {(g.profile_id, g.job_key): g for g in gold}, {})


def write_dataset(directory: Path, dataset=None):
    dataset = dataset or tiny_dataset()
    directory.mkdir(parents=True, exist_ok=True)
    def write(name, value):
        (directory / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    (directory / "jobs.jsonl").write_text("\n".join(r.model_dump_json() for r in dataset.records) + "\n", encoding="utf-8")
    write("profiles.json", {"schema_version": 1, "profiles": [p.model_dump(mode="json") for p in dataset.profiles]})
    (directory / "gold.jsonl").write_text("\n".join(g.model_dump_json() for g in dataset.gold.values()) + "\n", encoding="utf-8")
    write("algorithm_freeze.json", {"files": {name: digest(ROOT / name) for name in ALGORITHM_FILES}})
    refreeze(directory)
    return directory


def refreeze(directory):
    manifest = {"schema_version": 1, "source_hosts": ["careers.company.test"],
                "files": {name: digest(directory / name) for name in ("jobs.jsonl", "profiles.json", "gold.jsonl", "algorithm_freeze.json")}}
    (directory / "dataset_freeze.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_hand_calculated_precision_ndcg_and_exclusion():
    labels = {key: judgement(key, relevance=rel) for key, rel in [("a", 3), ("b", 2), ("c", 1), ("d", 0)]}
    result = score_ranking(["b", "c"], {"b", "c"}, labels, k=5)
    assert result["precision_at_k"] == 1 / 5
    expected = (3 + 1 / log2(3)) / (7 + 3 / log2(3) + 1 / log2(4))
    assert result["ndcg_at_k"] == pytest.approx(expected)
    assert result["false_excluded_useful_count"] == 1
    assert result["missed_useful_keys"] == ["a"]
    assert result["useful_retention_recall"] == .5


def test_underfilled_result_cannot_claim_perfect_precision():
    labels = {"a": judgement("a")}
    result = score_ranking(["a"], {"a"}, labels)
    assert result["precision_at_k"] == .2
    assert result["maximum_precision_at_k"] == .2
    assert result["display_fill_rate"] == .2
    assert result["ndcg_at_k"] == 1


def test_precision_ceiling_describes_pool_supply_without_changing_denominator():
    labels = {key: judgement(key, relevance=rel) for key, rel in [("a", 3), ("b", 2), ("c", 0)]}
    short = score_ranking(["a"], {"a"}, labels, k=5)
    assert short["maximum_precision_at_k"] == .4
    assert short["precision_at_k"] == .2  # Still divided by 5, not by the ceiling.
    assert short["precision_denominator"] == 5
    many = {str(i): judgement(str(i), relevance=2) for i in range(8)}
    full = score_ranking(list(many), set(many), many, k=5)
    assert full["maximum_precision_at_k"] == 1
    assert aggregate_metrics([short, full])["maximum_precision_at_k_macro"] == .7


def test_empty_and_zero_relevant_intent_have_explicit_denominators():
    labels = {"a": judgement("a", relevance=0)}
    empty = score_ranking([], set(), labels)
    assert empty["precision_at_k"] == 0
    assert empty["ndcg_at_k"] is None
    assert empty["useful_retention_recall"] is None
    assert empty["correct_empty_for_no_relevant"] is True
    summary = aggregate_metrics([empty])
    assert summary["ndcg_intent_denominator"] == 0
    assert summary["ndcg_at_k_macro"] is None
    assert summary["no_relevant_intents"] == 1
    assert summary["correct_empty_no_relevant_intents"] == 1


def test_below_display_cutoff_is_not_false_exclusion():
    labels = {str(i): judgement(str(i), relevance=2) for i in range(8)}
    result = score_ranking(list(labels), set(labels), labels)
    assert result["false_excluded_useful_count"] == 0
    assert len(result["relevant_below_top_k"]) == 3


def test_direction_and_qualification_failures_are_not_double_counted():
    labels = {"a": judgement("a", relevance=0, direction="unrelated", blocks=("degree",))}
    result = score_ranking(["a"], {"a"}, labels)
    assert result["wrong_direction_in_top_k"] == 1
    assert result["wrong_conditions_in_top_k"] == 1
    assert result["clearly_wrong_in_top_k"] == 1


@pytest.mark.parametrize("ordered,retained", [(["a", "a"], {"a"}), (["a"], {"a", "b"}), (["unknown"], {"unknown"})])
def test_duplicate_incomplete_or_unjudged_rankings_are_rejected(ordered, retained):
    with pytest.raises(ValueError):
        score_ranking(ordered, retained, {"a": judgement("a")})


def test_current_uses_production_filter_and_baseline_preserves_skill_only_errors():
    report = run_dataset(tiny_dataset())
    row = report["profiles"][0]
    assert row["systems"]["baseline"]["top_k"] == ["job-1", "job-2", "job-3"]
    assert row["systems"]["current"]["top_k"] == ["job-3"]
    assert row["systems"]["baseline"]["metrics"]["clearly_wrong_in_top_k"] == 2
    assert row["systems"]["current"]["metrics"]["clearly_wrong_in_top_k"] == 0
    assert row["systems"]["current"]["metrics"]["precision_at_k"] == .2
    assert row["production_counts"]["not_met"] == 1
    assert row["production_counts"]["direction_mismatch"] == 1
    assert row["direction_agreement"]["skipped_due_to_qualification_or_closed"] == 1
    assert report["eligibility_agreement"]["overall"]["total"] == 3
    assert report["eligibility_agreement"]["dimensions"]["degree"]["total"] == 3
    assert "0/1" in render_markdown(report)


def test_single_job_diagnostics_cover_beyond_service_limit_and_exclusion_sample_cap():
    base = tiny_dataset()
    jobs = [job(i, title="公关经理") for i in range(1, 61)] + [job(i) for i in range(61, 121)]
    records = [JobRecord(job_key=f"job-{j.id}", job=j) for j in jobs]
    labels = [judgement(r.job_key, relevance=0 if r.job.id <= 60 else 2,
                        direction="unrelated" if r.job.id <= 60 else "aligned", source=r.job) for r in records]
    corpus = Dataset(records, {r.job_key: r.job for r in records}, base.profiles,
                     {(g.profile_id, g.job_key): g for g in labels}, {})
    row = run_dataset(corpus)["profiles"][0]
    assert row["production_counts"]["evaluated"] == 120
    assert row["production_counts"]["direction_mismatch"] == 60
    assert len(row["systems"]["current"]["ranking"]) == 60
    assert row["systems"]["current"]["metrics"]["false_excluded_useful_count"] == 0
    assert len(row["current_diagnostics"]) == 120


def test_dataset_load_and_reports_are_deterministic_and_offline(tmp_path, monkeypatch):
    import socket
    def no_socket(*args, **kwargs):
        raise AssertionError("Offline evaluation must not open sockets")
    monkeypatch.setattr(socket, "socket", no_socket)
    directory = write_dataset(tmp_path / "data")
    first = run_dataset(load_dataset(directory))
    second = run_dataset(load_dataset(directory))
    assert first == second
    assert render_markdown(first) == render_markdown(second)
    json_path, md_path = tmp_path / "report.json", tmp_path / "report.md"
    assert main(["--dataset", str(directory), "--json", str(json_path), "--markdown", str(md_path)]) == 0
    assert json.loads(json_path.read_text(encoding="utf-8")) == first
    assert md_path.read_text(encoding="utf-8") == render_markdown(first)


@pytest.mark.parametrize("name", ["jobs.jsonl", "profiles.json", "gold.jsonl"])
def test_changed_frozen_input_is_rejected(tmp_path, name):
    directory = write_dataset(tmp_path / "data")
    with (directory / name).open("a", encoding="utf-8") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="SHA-256"):
        load_dataset(directory)


def test_rule_change_is_rejected(tmp_path):
    directory = write_dataset(tmp_path / "data")
    path = directory / "algorithm_freeze.json"
    data = json.loads(path.read_text())
    data["files"]["app/recommendations/quality.py"] = "0" * 64
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="SHA-256"):
        load_dataset(directory)


@pytest.mark.parametrize("frozen,runtime", [
    (b"VALUE = 1\r\nOTHER = 2\r\n", b"VALUE = 1\nOTHER = 2\n"),
    (b"VALUE = 1\nOTHER = 2\n", b"VALUE = 1\r\nOTHER = 2\r\n"),
])
def test_algorithm_lf_and_crlf_are_equivalent_without_rewriting_files(tmp_path, frozen, runtime):
    path = tmp_path / "algorithm.py"
    path.write_bytes(runtime)
    expected = {path.name: sha256(frozen).hexdigest()}
    _verify_files(tmp_path, expected, {path.name}, algorithm_line_endings=True)
    assert path.read_bytes() == runtime


def test_algorithm_content_change_is_rejected_even_with_line_ending_conversion(tmp_path):
    path = tmp_path / "algorithm.py"
    path.write_bytes(b"VALUE = 2\n")
    expected = {path.name: sha256(b"VALUE = 1\r\n").hexdigest()}
    with pytest.raises(ValueError, match="SHA-256"):
        _verify_files(tmp_path, expected, {path.name}, algorithm_line_endings=True)


def test_frozen_data_remains_byte_exact_across_line_endings(tmp_path):
    path = tmp_path / "jobs.jsonl"
    path.write_bytes(b'{"id": 1}\n{"id": 2}\n')
    expected = {path.name: sha256(b'{"id": 1}\r\n{"id": 2}\r\n').hexdigest()}
    with pytest.raises(ValueError, match="SHA-256"):
        _verify_files(tmp_path, expected, {path.name})
    # Even the algorithm option cannot relax a non-code file.
    with pytest.raises(ValueError, match="SHA-256"):
        _verify_files(tmp_path, expected, {path.name}, algorithm_line_endings=True)


def test_report_records_line_ending_policy_and_actual_source_hashes(tmp_path):
    dataset = load_dataset(write_dataset(tmp_path / "data"))
    assert dataset.fingerprints["algorithm_line_endings"] == ALGORITHM_LINE_ENDINGS_POLICY
    assert dataset.fingerprints["algorithm_actual_files"] == {
        name: digest(ROOT / name) for name in ALGORITHM_FILES
    }


def test_extra_algorithm_dependency_is_verified(tmp_path):
    directory = write_dataset(tmp_path / "data")
    path = directory / "algorithm_freeze.json"
    data = json.loads(path.read_text())
    data["files"]["app/services/deduplicator.py"] = digest(ROOT / "app/services/deduplicator.py")
    path.write_text(json.dumps(data))
    refreeze(directory)
    assert load_dataset(directory).primary
    data["files"]["app/services/deduplicator.py"] = "0" * 64
    path.write_text(json.dumps(data))
    refreeze(directory)
    with pytest.raises(ValueError, match="SHA-256"):
        load_dataset(directory)


@pytest.mark.parametrize("name", ["algorithm_freeze.json", "dataset_freeze.json"])
def test_nonobject_manifests_are_rejected_cleanly(tmp_path, name):
    directory = write_dataset(tmp_path / "data")
    (directory / name).write_text("[]")
    with pytest.raises(ValueError, match="JSON objects"):
        load_dataset(directory)


def test_default_algorithm_manifest_must_itself_be_frozen(tmp_path):
    directory = write_dataset(tmp_path / "data")
    path = directory / "dataset_freeze.json"
    manifest = json.loads(path.read_text())
    manifest["files"].pop("algorithm_freeze.json")
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="manifest must itself be frozen"):
        load_dataset(directory)


@pytest.mark.parametrize("case", ["duplicate_job", "missing_label", "duplicate_label", "bad_quote", "bad_offsets", "bad_host", "bad_enum", "inconsistent_overall", "bad_blocks", "bad_profile", "wrong_direction", "duplicate_json_field"])
def test_invalid_corpus_or_labels_are_rejected_after_hash_validation(tmp_path, case):
    directory = write_dataset(tmp_path / "data")
    if case == "duplicate_job":
        path = directory / "jobs.jsonl"
        path.write_text(path.read_text(encoding="utf-8") + path.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
    elif case == "duplicate_json_field":
        path = directory / "profiles.json"
        path.write_text(path.read_text(encoding="utf-8").replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'), encoding="utf-8")
    elif case == "bad_host":
        path = directory / "jobs.jsonl"
        path.write_text(path.read_text(encoding="utf-8").replace("careers.company.test", "unverified.test"), encoding="utf-8")
    else:
        path = directory / "gold.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        if case == "missing_label": rows.pop()
        elif case == "duplicate_label": rows.append(rows[0])
        elif case == "bad_quote": rows[0]["evidence"][0]["text"] = "不存在的原文"
        elif case == "bad_offsets": rows[0]["evidence"][0].update(start=1, end=3)
        elif case == "bad_enum": rows[0]["eligibility"]["city"] = "probably"
        elif case == "inconsistent_overall": rows[0]["overall"] = "met"
        elif case == "bad_blocks": rows[0]["hard_blocks"] = ["city"]
        elif case == "bad_profile": rows[0]["profile_id"] = "absent"
        elif case == "wrong_direction": rows[0]["direction"] = "not_requested"
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    refreeze(directory)
    with pytest.raises(ValueError):
        load_dataset(directory)


def test_report_cannot_overwrite_frozen_inputs(tmp_path):
    directory = write_dataset(tmp_path / "data")
    original = digest(directory / "jobs.jsonl")
    with pytest.raises(SystemExit):
        main(["--dataset", str(directory), "--json", str(directory / "jobs.jsonl"), "--markdown", str(tmp_path / "r.md")])
    assert digest(directory / "jobs.jsonl") == original
