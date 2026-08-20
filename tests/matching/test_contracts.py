from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.matching.contracts import (
    CandidateProfile,
    JobMatchResult,
    JobSkillEvidence,
    MatchReason,
)
from app.schemas.job_response import JobRead


def make_job() -> JobRead:
    return JobRead(
        id=1,
        title="Python后端实习生",
        company="示例科技",
        city="深圳",
        salary=None,
        description="负责后端开发。",
        skills=["Python", "FastAPI"],
        source="mock",
        source_url="https://example.com/jobs/1",
        published_at=date(2026, 8, 1),
        created_at=datetime(2026, 8, 1, 10, 0),
    )


def make_result(**overrides: object) -> JobMatchResult:
    data: dict[str, object] = {
        "job": make_job(),
        "match_score": 50,
        "matched_skills": ["Python"],
        "missing_skills": ["FastAPI"],
        "detected_job_skills": ["Python", "FastAPI"],
        "reason": MatchReason.PARTIAL_MATCH,
    }
    data.update(overrides)
    return JobMatchResult(**data)


def test_candidate_profile_normalizes_and_deduplicates_skills() -> None:
    profile = CandidateProfile(
        skills=[
            " python ",
            "FASTAPI",
            "Python",
            "  Distributed Systems  ",
        ]
    )

    assert profile.skills == [
        "Python",
        "FastAPI",
        "Distributed Systems",
    ]


def test_candidate_profile_requires_nonempty_skills() -> None:
    with pytest.raises(ValidationError):
        CandidateProfile(skills=[])

    with pytest.raises(ValidationError):
        CandidateProfile()


@pytest.mark.parametrize(
    "value",
    [
        ["   "],
        [1],
        ["Python", 1],
    ],
)
def test_candidate_profile_rejects_invalid_skills(value: object) -> None:
    with pytest.raises(ValidationError):
        CandidateProfile(skills=value)


def test_candidate_profile_normalizes_and_deduplicates_cities() -> None:
    profile = CandidateProfile(
        skills=["Python"],
        preferred_cities=[" 北京市 ", "北京", "东莞市"],
    )

    assert profile.preferred_cities == ["北京", "东莞"]


def test_candidate_profile_defaults_to_empty_cities() -> None:
    assert CandidateProfile(skills=["Python"]).preferred_cities == []


@pytest.mark.parametrize(
    "value",
    [
        ["   "],
        [1],
        ["深圳", 1],
    ],
)
def test_candidate_profile_rejects_invalid_cities(value: object) -> None:
    with pytest.raises(ValidationError):
        CandidateProfile(skills=["Python"], preferred_cities=value)


def test_candidate_profile_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CandidateProfile(skills=["Python"], unexpected=True)


def test_job_skill_evidence_allows_empty_evidence() -> None:
    assert JobSkillEvidence(skills=[]).skills == []


def test_job_skill_evidence_requires_skills() -> None:
    with pytest.raises(ValidationError):
        JobSkillEvidence()


def test_job_skill_evidence_normalizes_and_deduplicates() -> None:
    evidence = JobSkillEvidence(
        skills=[" python ", "PYTHON", "BeautifulSoup4", "Unknown"]
    )

    assert evidence.skills == [
        "Python",
        "Beautiful Soup",
        "Unknown",
    ]


@pytest.mark.parametrize("value", [["   "], [1], ["Python", 1]])
def test_job_skill_evidence_rejects_invalid_values(value: object) -> None:
    with pytest.raises(ValidationError):
        JobSkillEvidence(skills=value)


def test_job_skill_evidence_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        JobSkillEvidence(skills=[], source="title")


def test_match_reason_values_are_string_compatible() -> None:
    assert [reason.value for reason in MatchReason] == [
        "full_match",
        "partial_match",
        "no_skill_match",
        "insufficient_evidence",
    ]


@pytest.mark.parametrize("score", [0, 50, 100])
def test_job_match_result_accepts_valid_integer_scores(score: int) -> None:
    assert make_result(match_score=score).match_score == score


@pytest.mark.parametrize("score", [-1, 101, "50", 50.0, True])
def test_job_match_result_rejects_invalid_scores(score: object) -> None:
    with pytest.raises(ValidationError):
        make_result(match_score=score)


@pytest.mark.parametrize(
    "field",
    ["matched_skills", "missing_skills", "detected_job_skills"],
)
def test_job_match_result_requires_skill_lists(field: str) -> None:
    data = {
        "job": make_job(),
        "match_score": 0,
        "matched_skills": [],
        "missing_skills": [],
        "detected_job_skills": [],
        "reason": MatchReason.INSUFFICIENT_EVIDENCE,
    }
    del data[field]

    with pytest.raises(ValidationError):
        JobMatchResult(**data)


def test_job_match_result_accepts_zero_evidence() -> None:
    result = make_result(
        match_score=0,
        matched_skills=[],
        missing_skills=[],
        detected_job_skills=[],
        reason=MatchReason.INSUFFICIENT_EVIDENCE,
    )

    assert result.detected_job_skills == []


def test_job_match_result_normalizes_skill_lists() -> None:
    result = make_result(
        matched_skills=[" python ", "PYTHON"],
        missing_skills=["FASTAPI"],
        detected_job_skills=["Python", "fastapi"],
    )

    assert result.matched_skills == ["Python"]
    assert result.missing_skills == ["FastAPI"]
    assert result.detected_job_skills == ["Python", "FastAPI"]


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "matched_skills": ["Python"],
            "missing_skills": ["python"],
        },
        {
            "matched_skills": ["SQL"],
        },
        {
            "missing_skills": ["SQL"],
        },
        {
            "matched_skills": ["Python"],
            "missing_skills": [],
        },
    ],
)
def test_job_match_result_rejects_invalid_skill_partition(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        make_result(**overrides)


def test_job_match_result_rejects_invalid_reason() -> None:
    with pytest.raises(ValidationError):
        make_result(reason="unsupported_reason")


def test_job_match_result_serializes_to_json_compatible_data() -> None:
    result = make_result()

    data = result.model_dump(mode="json")

    assert data["reason"] == "partial_match"
    assert data["job"]["published_at"] == "2026-08-01"
    assert data["match_score"] == 50
