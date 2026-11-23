"""Validate the frozen recommendation corpus, independent labels and rule fingerprints."""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from app.eligibility.contracts import DecisionStatus, Dimension
from app.recommendations.contracts import RecommendationCandidate
from app.recommendations.identity import group_jobs, is_sample_record
from app.schemas.job_response import JobRead


ROOT = Path(__file__).resolve().parents[1]
ALGORITHM_FILES = {
    "app/matching/matcher.py", "app/matching/skill_extractor.py", "app/services/skill_vocabulary.py",
    "app/recommendations/service.py", "app/recommendations/quality.py", "app/recommendations/identity.py",
    "app/eligibility/extractor.py", "app/eligibility/evaluator.py",
}
DATA_FILES = {"jobs.jsonl", "profiles.json", "gold.jsonl"}
DIMENSIONS = ("graduation_year", "degree", "experience", "city", "internship_duration")
STATES = ("met", "not_met", "unknown")
ALGORITHM_LINE_ENDINGS_POLICY = (
    "Frozen algorithm .py files accept LF/CRLF-only line-ending equivalence; "
    "all other source bytes and all frozen dataset files remain byte-exact. "
    "algorithm_files records frozen hashes; algorithm_actual_files records runtime byte hashes."
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Profile(FrozenModel):
    profile_id: StrictStr = Field(min_length=1)
    label: StrictStr = Field(min_length=1)
    candidate: RecommendationCandidate


class ProfileFile(FrozenModel):
    schema_version: Literal[1]
    profiles: list[Profile] = Field(min_length=1)


class JobRecord(FrozenModel):
    job_key: StrictStr = Field(min_length=1)
    job: JobRead
    metadata: dict = Field(default_factory=dict)


class Quote(FrozenModel):
    field: Literal["title", "description", "city"]
    text: StrictStr = Field(min_length=1)
    start: StrictInt | None = Field(default=None, ge=0)
    end: StrictInt | None = Field(default=None, gt=0)


class Gold(FrozenModel):
    profile_id: StrictStr = Field(min_length=1)
    job_key: StrictStr = Field(min_length=1)
    direction: Literal["aligned", "uncertain", "unrelated", "not_requested"]
    eligibility: dict[Dimension, DecisionStatus]
    overall: DecisionStatus
    relevance: StrictInt = Field(ge=0, le=3)
    hard_blocks: list[Dimension]
    reason: StrictStr = Field(min_length=1)
    evidence: list[Quote] = Field(min_length=1)


@dataclass
class Dataset:
    records: list[JobRecord]
    primary: dict[str, JobRead]
    profiles: list[Profile]
    gold: dict[tuple[str, str], Gold]
    fingerprints: dict


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _decode(text: str):
    return json.loads(text, object_pairs_hook=_unique_fields)


def _json(path: Path):
    return _decode(path.read_text(encoding="utf-8-sig"))


def _rows(path: Path, cls):
    rows = []
    for index, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if line.strip():
            try:
                rows.append(cls.model_validate(_decode(line)))
            except ValueError as exc:
                raise ValueError(f"{path.name}, line {index}: {exc}") from exc
    if not rows:
        raise ValueError(f"Empty holdout input: {path.name}")
    return rows


def _verify_files(
    directory: Path, entries: dict, required: set[str], *, exact: bool = False,
    algorithm_line_endings: bool = False,
):
    if not isinstance(entries, dict) or not required.issubset(entries) or (exact and set(entries) != required):
        raise ValueError("Invalid or incomplete set of frozen file hashes.")
    for name, expected in entries.items():
        relative = Path(name)
        path = (directory / relative).resolve()
        if relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(directory.resolve()):
            raise ValueError(f"Invalid frozen relative path: {name}")
        if not path.is_file():
            raise ValueError(f"Frozen file is missing or its SHA-256 differs: {name}")
        raw = path.read_bytes()
        candidates = {sha256(raw).hexdigest()}
        if algorithm_line_endings and path.suffix == ".py":
            # Git commonly checks the same Python source out as LF on Linux and
            # CRLF on Windows. Do not rewrite the frozen files or accept any
            # other byte difference (including whitespace, BOMs or lone CRs).
            lf = raw.replace(b"\r\n", b"\n")
            candidates.update((sha256(lf).hexdigest(), sha256(lf.replace(b"\n", b"\r\n")).hexdigest()))
        if expected not in candidates:
            raise ValueError(f"Frozen file is missing or its SHA-256 differs: {name}")


def _verify_gold(gold: Gold, profile: Profile, job: JobRead):
    if not gold.reason.strip() or set(gold.eligibility) != set(DIMENSIONS):
        raise ValueError("Gold labels need a rationale and all five dimensions.")
    blocked = {dim for dim, value in gold.eligibility.items() if value == "not_met"}
    if set(gold.hard_blocks) != blocked or len(gold.hard_blocks) != len(blocked):
        raise ValueError("Gold hard_blocks disagree with the five dimension labels.")
    expected = ("not_met" if blocked or job.status == "closed" else
                "unknown" if "unknown" in gold.eligibility.values() else "met")
    if gold.overall != expected:
        raise ValueError("Overall gold label disagrees with condition labels or closure.")
    if bool(profile.candidate.target_directions) == (gold.direction == "not_requested"):
        raise ValueError("Gold direction disagrees with whether the intent specified targets.")
    if (gold.overall == "not_met" or gold.direction == "unrelated") and gold.relevance != 0:
        raise ValueError("Clearly blocked or unrelated jobs must have relevance zero.")
    for quote in gold.evidence:
        text = getattr(job, quote.field)
        if not quote.text.strip() or quote.text not in text:
            raise ValueError("Gold evidence does not occur in the frozen source field.")
        if quote.start is None and quote.end is None:
            continue
        if (quote.start is None or quote.end is None or not 0 <= quote.start < quote.end <= len(text)
                or text[quote.start:quote.end] != quote.text):
            raise ValueError("Invalid gold evidence offsets for the frozen source field.")


def load_dataset(
    directory: Path, *, algorithm_root: Path | None = None,
    algorithm_manifest: str = "algorithm_freeze.json",
) -> Dataset:
    directory = Path(directory).resolve()
    source_root = Path(algorithm_root).resolve() if algorithm_root is not None else ROOT
    algorithm_path = (directory / algorithm_manifest).resolve()
    if algorithm_path.parent != directory or not algorithm_manifest.endswith(".json"):
        raise ValueError("The algorithm manifest must be one JSON file inside the frozen dataset.")
    algorithm = _json(algorithm_path)
    manifest = _json(directory / "dataset_freeze.json")
    if not isinstance(algorithm, dict) or not isinstance(manifest, dict):
        raise ValueError("Frozen manifests must be JSON objects.")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ValueError("Unsupported dataset freeze version.")
    _verify_files(directory, manifest.get("files"), DATA_FILES)
    if algorithm_manifest not in manifest["files"]:
        raise ValueError("The selected algorithm manifest must itself be frozen.")
    _verify_files(source_root, algorithm.get("files"), ALGORITHM_FILES, algorithm_line_endings=True)
    hosts = manifest.get("source_hosts")
    if not isinstance(hosts, list) or not hosts or any(
        not isinstance(host, str) or not host or host != host.strip().casefold() or any(c in host for c in "/:@*")
        for host in hosts
    ):
        raise ValueError("source_hosts must list exact lowercase official host names.")
    records = _rows(directory / "jobs.jsonl", JobRecord)
    profiles = ProfileFile.model_validate(_json(directory / "profiles.json")).profiles
    if len({r.job.id for r in records}) != len(records) or len({r.job_key for r in records}) != len(records):
        raise ValueError("Duplicate job ID or stable job key.")
    if len({p.profile_id for p in profiles}) != len(profiles):
        raise ValueError("Duplicate profile ID.")
    if any(not p.profile_id.strip() or not p.label.strip() for p in profiles):
        raise ValueError("Profiles require nonempty IDs and display labels.")
    for record in records:
        job = record.job
        if job.id < 1 or not record.job_key.strip():
            raise ValueError("Frozen jobs require positive IDs and nonempty keys.")
        if any(not getattr(job, name).strip() for name in ("title", "company", "city", "description", "source")):
            raise ValueError("Frozen jobs require source text, company, title and city.")
        if not is_sample_record(job):
            parsed = urlsplit(job.source_url)
            if (parsed.scheme not in {"http", "https"} or parsed.hostname not in hosts
                    or parsed.username is not None or parsed.password is not None):
                raise ValueError(f"Source outside the frozen official host list: {record.job_key}")
            _ = parsed.port  # Reject malformed ports, as does the identity function.
    id_to_key = {r.job.id: r.job_key for r in records}
    groups = group_jobs([r.job for r in records if not is_sample_record(r.job)])
    primary = {id_to_key[group.primary.id]: group.primary for group in groups}
    if not primary:
        raise ValueError("No independent, nonsample jobs in the holdout pool.")
    by_profile = {p.profile_id: p for p in profiles}
    labels = {}
    for item in _rows(directory / "gold.jsonl", Gold):
        key = (item.profile_id, item.job_key)
        if key in labels or item.profile_id not in by_profile or item.job_key not in primary:
            raise ValueError(f"Duplicate or out-of-pool judgement: {key}")
        try:
            _verify_gold(item, by_profile[item.profile_id], primary[item.job_key])
        except ValueError as exc:
            raise ValueError(f"Invalid label for {key}: {exc}") from exc
        labels[key] = item
    if len(labels) != len(by_profile) * len(primary):
        raise ValueError("Incomplete labels: every intent and independent job pair must be judged.")
    return Dataset(records, primary, profiles, labels, {
        "data_files": manifest["files"], "algorithm_files": algorithm["files"],
        "algorithm_line_endings": ALGORITHM_LINE_ENDINGS_POLICY,
        "algorithm_actual_files": {name: digest(source_root / name) for name in algorithm["files"]},
        "dataset_manifest_sha256": digest(directory / "dataset_freeze.json"),
        "algorithm_manifest_sha256": digest(algorithm_path),
        "algorithm_manifest": algorithm_manifest,
    })
