from datetime import date, datetime

import pytest

from app.matching.contracts import (
    CandidateProfile,
    JobSkillEvidence,
    MatchReason,
)
from app.matching.matcher import CandidateMatcher
from app.schemas.job_response import JobRead


def make_job(**overrides: object) -> JobRead:
    data: dict[str, object] = {
        "id": 1,
        "title": "产品实习生",
        "company": "示例科技",
        "city": "深圳",
        "salary": None,
        "description": "负责产品调研与需求分析。",
        "skills": [],
        "source": "mock",
        "source_url": "https://example.com/jobs/1",
        "published_at": date(2026, 8, 1),
        "created_at": datetime(2026, 8, 1, 10, 0),
    }
    data.update(overrides)
    return JobRead(**data)


@pytest.mark.parametrize(
    "skills",
    [
        ["Python"],
        ["Python", "SQL", "FastAPI"],
    ],
)
def test_full_match_for_one_or_multiple_skills(
    skills: list[str],
) -> None:
    result = CandidateMatcher().match(
        candidate=CandidateProfile(skills=list(reversed(skills))),
        job=make_job(),
        evidence=JobSkillEvidence(skills=skills),
    )

    assert result.matched_skills == skills
    assert result.missing_skills == []
    assert result.detected_job_skills == skills
    assert result.match_score == 100
    assert result.reason is MatchReason.FULL_MATCH


@pytest.mark.parametrize(
    (
        "candidate_skills",
        "evidence_skills",
        "expected_matched",
        "expected_missing",
        "expected_score",
    ),
    [
        (
            ["Python"],
            ["Python", "SQL", "Docker"],
            ["Python"],
            ["SQL", "Docker"],
            33,
        ),
        (
            ["Docker", "Python", "FastAPI"],
            ["Python", "SQL", "FastAPI", "Git", "Docker"],
            ["Python", "FastAPI", "Docker"],
            ["SQL", "Git"],
            60,
        ),
    ],
)
def test_partial_match_partitions_detected_skills(
    candidate_skills: list[str],
    evidence_skills: list[str],
    expected_matched: list[str],
    expected_missing: list[str],
    expected_score: int,
) -> None:
    result = CandidateMatcher().match(
        candidate=CandidateProfile(skills=candidate_skills),
        job=make_job(),
        evidence=JobSkillEvidence(skills=evidence_skills),
    )

    assert result.matched_skills == expected_matched
    assert result.missing_skills == expected_missing
    assert result.match_score == expected_score
    assert result.reason is MatchReason.PARTIAL_MATCH


def test_no_skill_match_preserves_all_evidence_as_missing() -> None:
    result = CandidateMatcher().match(
        candidate=CandidateProfile(skills=["Java"]),
        job=make_job(),
        evidence=JobSkillEvidence(skills=["Python", "SQL"]),
    )

    assert result.matched_skills == []
    assert result.missing_skills == ["Python", "SQL"]
    assert result.detected_job_skills == ["Python", "SQL"]
    assert result.match_score == 0
    assert result.reason is MatchReason.NO_SKILL_MATCH


def test_zero_evidence_is_insufficient_evidence() -> None:
    result = CandidateMatcher().match(
        candidate=CandidateProfile(skills=["Python"]),
        job=make_job(),
        evidence=JobSkillEvidence(skills=[]),
    )

    assert result.match_score == 0
    assert result.matched_skills == []
    assert result.missing_skills == []
    assert result.detected_job_skills == []
    assert result.reason is MatchReason.INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize(
    ("matched_count", "detected_count", "expected_score"),
    [
        (1, 3, 33),
        (2, 3, 67),
        (1, 6, 17),
        (5, 6, 83),
        (1, 8, 13),
        (3, 8, 38),
        (7, 8, 88),
    ],
)
def test_match_score_uses_half_up_integer_rounding(
    matched_count: int,
    detected_count: int,
    expected_score: int,
) -> None:
    evidence_skills = [
        f"Detected Skill {index}"
        for index in range(detected_count)
    ]
    candidate_skills = evidence_skills[:matched_count]

    result = CandidateMatcher().match(
        candidate=CandidateProfile(skills=candidate_skills),
        job=make_job(),
        evidence=JobSkillEvidence(skills=evidence_skills),
    )

    assert result.match_score == expected_score
    assert result.reason is MatchReason.PARTIAL_MATCH


def test_evidence_order_controls_every_result_skill_list() -> None:
    result = CandidateMatcher().match(
        candidate=CandidateProfile(
            skills=["FastAPI", "Python", "Kubernetes"]
        ),
        job=make_job(),
        evidence=JobSkillEvidence(
            skills=["Python", "SQL", "FastAPI", "Kubernetes"]
        ),
    )

    assert result.matched_skills == [
        "Python",
        "FastAPI",
        "Kubernetes",
    ]
    assert result.missing_skills == ["SQL"]
    assert result.detected_job_skills == [
        "Python",
        "SQL",
        "FastAPI",
        "Kubernetes",
    ]


@pytest.mark.parametrize("candidate_skill", ["Kubernetes", "kubernetes"])
def test_unknown_skills_match_case_insensitively_with_evidence_spelling(
    candidate_skill: str,
) -> None:
    result = CandidateMatcher().match(
        candidate=CandidateProfile(skills=[candidate_skill]),
        job=make_job(),
        evidence=JobSkillEvidence(skills=["Kubernetes"]),
    )

    assert result.matched_skills == ["Kubernetes"]
    assert result.missing_skills == []
    assert result.match_score == 100
    assert result.reason is MatchReason.FULL_MATCH


def test_result_preserves_job_and_exactly_partitions_evidence() -> None:
    job = make_job(id=7)
    evidence = JobSkillEvidence(
        skills=["Python", "SQL", "FastAPI", "Docker"]
    )

    result = CandidateMatcher().match(
        candidate=CandidateProfile(skills=["Docker", "Python"]),
        job=job,
        evidence=evidence,
    )

    detected = {skill.casefold() for skill in result.detected_job_skills}
    matched = {skill.casefold() for skill in result.matched_skills}
    missing = {skill.casefold() for skill in result.missing_skills}

    assert result.job == job
    assert matched.isdisjoint(missing)
    assert matched | missing == detected
    assert len(result.matched_skills) + len(result.missing_skills) == len(
        evidence.skills
    )


def test_matcher_does_not_mutate_inputs_and_is_repeatable() -> None:
    candidate = CandidateProfile(
        skills=["FastAPI", "Python"],
        preferred_cities=["深圳"],
    )
    job = make_job(
        title="Python实习生",
        description="使用FastAPI和SQL。",
        skills=["Python"],
    )
    evidence = JobSkillEvidence(skills=["Python", "FastAPI", "SQL"])
    candidate_before = candidate.model_dump(mode="python")
    job_before = job.model_dump(mode="python")
    evidence_before = evidence.model_dump(mode="python")
    matcher = CandidateMatcher()

    first = matcher.match(candidate=candidate, job=job, evidence=evidence)
    second = matcher.match(candidate=candidate, job=job, evidence=evidence)

    assert first == second
    assert candidate.model_dump(mode="python") == candidate_before
    assert job.model_dump(mode="python") == job_before
    assert evidence.model_dump(mode="python") == evidence_before


def test_reason_uses_counts_when_partial_score_rounds_to_zero() -> None:
    evidence_skills = [
        f"Detected Skill {index}" for index in range(201)
    ]

    result = CandidateMatcher().match(
        candidate=CandidateProfile(skills=[evidence_skills[0]]),
        job=make_job(),
        evidence=JobSkillEvidence(skills=evidence_skills),
    )

    assert result.match_score == 0
    assert result.reason is MatchReason.PARTIAL_MATCH


def test_reason_uses_counts_when_partial_score_rounds_to_one_hundred() -> None:
    evidence_skills = [
        f"Detected Skill {index}" for index in range(201)
    ]

    result = CandidateMatcher().match(
        candidate=CandidateProfile(skills=evidence_skills[:-1]),
        job=make_job(),
        evidence=JobSkillEvidence(skills=evidence_skills),
    )

    assert result.match_score == 100
    assert result.reason is MatchReason.PARTIAL_MATCH


def test_empty_evidence_remains_authoritative_over_job_text() -> None:
    result = CandidateMatcher().match(
        candidate=CandidateProfile(skills=["Python"]),
        job=make_job(
            title="Python开发实习生",
            description="负责Python和FastAPI开发。",
            skills=["Python"],
        ),
        evidence=JobSkillEvidence(skills=[]),
    )

    assert result.match_score == 0
    assert result.matched_skills == []
    assert result.missing_skills == []
    assert result.reason is MatchReason.INSUFFICIENT_EVIDENCE


def test_matching_uses_evidence_even_when_job_prose_differs() -> None:
    result = CandidateMatcher().match(
        candidate=CandidateProfile(skills=["Kubernetes"]),
        job=make_job(
            title="Java开发实习生",
            description="负责SQL数据处理。",
            skills=["Java", "SQL"],
        ),
        evidence=JobSkillEvidence(skills=["Kubernetes"]),
    )

    assert result.matched_skills == ["Kubernetes"]
    assert result.match_score == 100
    assert result.reason is MatchReason.FULL_MATCH
