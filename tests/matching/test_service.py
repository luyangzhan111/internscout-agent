from datetime import date, datetime
from typing import Any

import pytest

from app.agent.tools.job_query import JobQueryPort
from app.matching.contracts import (
    CandidateProfile,
    JobMatchResult,
    JobSkillEvidence,
    MatchReason,
)
from app.matching.matcher import CandidateMatcher
from app.matching.service import PAGE_SIZE, JobMatchingService
from app.matching.skill_extractor import JobSkillExtractor
from app.schemas.job_response import JobRead


def make_job(
    job_id: int,
    **overrides: object,
) -> JobRead:
    data: dict[str, object] = {
        "id": job_id,
        "title": f"岗位 {job_id}",
        "company": "示例科技",
        "city": "深圳",
        "salary": None,
        "description": "负责产品调研与需求分析。",
        "skills": [],
        "source": "mock",
        "source_url": f"https://example.com/jobs/{job_id}",
        "published_at": date(2026, 8, 1),
        "created_at": datetime(2026, 8, 1, 10, 0),
    }
    data.update(overrides)
    return JobRead(**data)


def make_jobs(count: int) -> list[JobRead]:
    return [make_job(job_id) for job_id in range(1, count + 1)]


def make_result(
    job: JobRead,
    *,
    score: int,
    matched: list[str],
    missing: list[str],
    reason: MatchReason = MatchReason.PARTIAL_MATCH,
) -> JobMatchResult:
    return JobMatchResult(
        job=job,
        match_score=score,
        matched_skills=matched,
        missing_skills=missing,
        detected_job_skills=matched + missing,
        reason=reason,
    )


class FakeJobQuery(JobQueryPort):
    def __init__(
        self,
        jobs: list[JobRead] | None = None,
        *,
        total: int | None = None,
        pages: dict[int, list[JobRead]] | None = None,
        totals_by_page: dict[int, int] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.jobs = jobs or []
        self.total = len(self.jobs) if total is None else total
        self.pages = pages
        self.totals_by_page = totals_by_page or {}
        self.error = error
        self.search_calls: list[dict[str, object]] = []

    def search_jobs(
        self,
        *,
        city: str | None = None,
        company: str | None = None,
        skill: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[JobRead], int]:
        self.search_calls.append(
            {
                "city": city,
                "company": company,
                "skill": skill,
                "page": page,
                "page_size": page_size,
            }
        )

        if self.error is not None:
            raise self.error

        if self.pages is not None:
            items = list(self.pages.get(page, []))
        else:
            start = (page - 1) * page_size
            items = list(self.jobs[start:start + page_size])

        return items, self.totals_by_page.get(page, self.total)

    def get_job_by_id(self, job_id: int) -> JobRead | None:
        return next(
            (job for job in self.jobs if job.id == job_id),
            None,
        )


class RecordingExtractor(JobSkillExtractor):
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[JobRead] = []
        self.error = error

    def extract(self, job: JobRead) -> JobSkillEvidence:
        self.calls.append(job)

        if self.error is not None:
            raise self.error

        return super().extract(job)


class RecordingMatcher(CandidateMatcher):
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[
            tuple[CandidateProfile, JobRead, JobSkillEvidence]
        ] = []
        self.error = error

    def match(
        self,
        *,
        candidate: CandidateProfile,
        job: JobRead,
        evidence: JobSkillEvidence,
    ) -> JobMatchResult:
        self.calls.append((candidate, job, evidence))

        if self.error is not None:
            raise self.error

        return super().match(
            candidate=candidate,
            job=job,
            evidence=evidence,
        )


class StubExtractor(JobSkillExtractor):
    def __init__(self, evidence: JobSkillEvidence) -> None:
        self.evidence = evidence
        self.calls: list[JobRead] = []

    def extract(self, job: JobRead) -> JobSkillEvidence:
        self.calls.append(job)
        return self.evidence


class StubMatcher(CandidateMatcher):
    def __init__(self, result: JobMatchResult) -> None:
        self.result = result
        self.calls: list[
            tuple[CandidateProfile, JobRead, JobSkillEvidence]
        ] = []

    def match(
        self,
        *,
        candidate: CandidateProfile,
        job: JobRead,
        evidence: JobSkillEvidence,
    ) -> JobMatchResult:
        self.calls.append((candidate, job, evidence))
        return self.result


class ResultMappingMatcher(CandidateMatcher):
    def __init__(self, results: dict[int, JobMatchResult]) -> None:
        self.results = results

    def match(
        self,
        *,
        candidate: CandidateProfile,
        job: JobRead,
        evidence: JobSkillEvidence,
    ) -> JobMatchResult:
        return self.results[job.id]


def make_service(
    job_query: JobQueryPort,
    *,
    extractor: JobSkillExtractor | None = None,
    matcher: CandidateMatcher | None = None,
) -> JobMatchingService:
    return JobMatchingService(
        job_query=job_query,
        skill_extractor=extractor or JobSkillExtractor(),
        matcher=matcher or CandidateMatcher(),
    )


def requested_pages(job_query: FakeJobQuery) -> list[int]:
    return [int(call["page"]) for call in job_query.search_calls]


def test_service_orchestrates_query_extraction_and_matching() -> None:
    jobs = [
        make_job(1, skills=["Python"]),
        make_job(2, skills=["SQL"]),
    ]
    job_query = FakeJobQuery(jobs)
    extractor = RecordingExtractor()
    matcher = RecordingMatcher()

    results = make_service(
        job_query,
        extractor=extractor,
        matcher=matcher,
    ).match_jobs(
        candidate=CandidateProfile(skills=["Python"]),
        top_k=10,
    )

    assert job_query.search_calls == [
        {
            "city": None,
            "company": None,
            "skill": None,
            "page": 1,
            "page_size": PAGE_SIZE,
        }
    ]
    assert [job.id for job in extractor.calls] == [1, 2]
    assert [call[1].id for call in matcher.calls] == [1, 2]
    assert all(isinstance(result, JobMatchResult) for result in results)
    assert [result.job.id for result in results] == [1, 2]


def test_zero_jobs_returns_empty_without_collaborator_calls() -> None:
    job_query = FakeJobQuery()
    extractor = RecordingExtractor()
    matcher = RecordingMatcher()

    results = make_service(
        job_query,
        extractor=extractor,
        matcher=matcher,
    ).match_jobs(
        candidate=CandidateProfile(skills=["Python"]),
        top_k=10,
    )

    assert results == []
    assert requested_pages(job_query) == [1]
    assert extractor.calls == []
    assert matcher.calls == []


@pytest.mark.parametrize(
    ("preferred_cities", "expected_ids"),
    [
        ([], [1, 2, 3]),
        (["深圳"], [1]),
        (["深圳", "东莞"], [1, 3]),
        (["北京"], []),
    ],
)
def test_preferred_city_eligibility(
    preferred_cities: list[str],
    expected_ids: list[int],
) -> None:
    jobs = [
        make_job(1, city="深圳"),
        make_job(2, city="上海"),
        make_job(3, city="东莞"),
    ]
    extractor = RecordingExtractor()
    matcher = RecordingMatcher()

    results = make_service(
        FakeJobQuery(jobs),
        extractor=extractor,
        matcher=matcher,
    ).match_jobs(
        candidate=CandidateProfile(
            skills=["Python"],
            preferred_cities=preferred_cities,
        ),
        top_k=10,
    )

    assert [result.job.id for result in results] == expected_ids
    assert [job.id for job in extractor.calls] == expected_ids
    assert [call[1].id for call in matcher.calls] == expected_ids


def test_city_comparison_is_case_insensitive() -> None:
    job = make_job(1, city="ShEnZhEn", skills=["Python"])

    results = make_service(FakeJobQuery([job])).match_jobs(
        candidate=CandidateProfile(
            skills=["Python"],
            preferred_cities=["shenzhen"],
        ),
        top_k=1,
    )

    assert [result.job.id for result in results] == [1]


def test_city_restriction_does_not_change_match_score() -> None:
    job = make_job(1, city="深圳", skills=["Python", "SQL"])
    unrestricted = make_service(FakeJobQuery([job])).match_jobs(
        candidate=CandidateProfile(skills=["Python"]),
        top_k=1,
    )
    restricted = make_service(FakeJobQuery([job])).match_jobs(
        candidate=CandidateProfile(
            skills=["Python"],
            preferred_cities=["深圳"],
        ),
        top_k=1,
    )

    assert unrestricted[0].match_score == restricted[0].match_score == 50
    assert unrestricted[0].reason is restricted[0].reason


@pytest.mark.parametrize(
    ("job_count", "expected_pages"),
    [
        (1, [1]),
        (PAGE_SIZE + 1, [1, 2]),
        (PAGE_SIZE * 2, [1, 2]),
        (PAGE_SIZE * 2 + 1, [1, 2, 3]),
    ],
)
def test_service_requests_every_page_from_first_total(
    job_count: int,
    expected_pages: list[int],
) -> None:
    job_query = FakeJobQuery(make_jobs(job_count))

    results = make_service(job_query).match_jobs(
        candidate=CandidateProfile(skills=["Python"]),
        top_k=job_count,
    )

    assert len(results) == job_count
    assert requested_pages(job_query) == expected_pages
    assert all(
        call["page_size"] == PAGE_SIZE
        for call in job_query.search_calls
    )


def test_strongest_job_beyond_first_page_can_rank_first() -> None:
    jobs = make_jobs(PAGE_SIZE)
    jobs.append(make_job(PAGE_SIZE + 1, skills=["Python"]))
    job_query = FakeJobQuery(jobs)

    results = make_service(job_query).match_jobs(
        candidate=CandidateProfile(skills=["Python"]),
        top_k=1,
    )

    assert requested_pages(job_query) == [1, 2]
    assert [result.job.id for result in results] == [PAGE_SIZE + 1]
    assert results[0].match_score == 100


@pytest.mark.parametrize(
    "intermediate_page",
    [
        [],
        [make_job(2)],
    ],
)
def test_fixed_horizon_ignores_empty_or_short_intermediate_page(
    intermediate_page: list[JobRead],
) -> None:
    job_query = FakeJobQuery(
        total=PAGE_SIZE * 2 + 1,
        pages={
            1: [make_job(1)],
            2: intermediate_page,
            3: [make_job(3, skills=["Python"])],
        },
        totals_by_page={
            2: 0,
            3: PAGE_SIZE * 10,
        },
    )

    results = make_service(job_query).match_jobs(
        candidate=CandidateProfile(skills=["Python"]),
        top_k=10,
    )

    assert requested_pages(job_query) == [1, 2, 3]
    assert results[0].job.id == 3


def test_duplicate_job_id_uses_first_occurrence_once() -> None:
    first = make_job(1, skills=["Python"])
    duplicate = make_job(1, skills=["SQL"])
    job_query = FakeJobQuery(
        total=PAGE_SIZE + 1,
        pages={1: [first], 2: [duplicate]},
    )
    extractor = RecordingExtractor()
    matcher = RecordingMatcher()

    results = make_service(
        job_query,
        extractor=extractor,
        matcher=matcher,
    ).match_jobs(
        candidate=CandidateProfile(skills=["Python"]),
        top_k=10,
    )

    assert len(results) == 1
    assert results[0].job is first
    assert results[0].detected_job_skills == ["Python"]
    assert extractor.calls == [first]
    assert len(matcher.calls) == 1


def test_ranking_prefers_higher_match_score() -> None:
    low = make_job(1)
    high = make_job(2)
    matcher = ResultMappingMatcher(
        {
            1: make_result(
                low,
                score=0,
                matched=[],
                missing=["Python"],
                reason=MatchReason.NO_SKILL_MATCH,
            ),
            2: make_result(
                high,
                score=100,
                matched=["Python"],
                missing=[],
                reason=MatchReason.FULL_MATCH,
            ),
        }
    )

    results = make_service(
        FakeJobQuery([low, high]),
        matcher=matcher,
    ).match_jobs(
        candidate=CandidateProfile(skills=["Python"]),
        top_k=2,
    )

    assert [result.job.id for result in results] == [2, 1]


def test_ranking_prefers_more_matched_skills_for_equal_score() -> None:
    one_match = make_job(1)
    two_matches = make_job(2)
    matcher = ResultMappingMatcher(
        {
            1: make_result(
                one_match,
                score=50,
                matched=["Python"],
                missing=["SQL"],
            ),
            2: make_result(
                two_matches,
                score=50,
                matched=["Python", "Git"],
                missing=["SQL", "Docker"],
            ),
        }
    )

    results = make_service(
        FakeJobQuery([one_match, two_matches]),
        matcher=matcher,
    ).match_jobs(
        candidate=CandidateProfile(skills=["Python"]),
        top_k=2,
    )

    assert [result.job.id for result in results] == [2, 1]


def test_final_ranking_tie_uses_numeric_job_id_only() -> None:
    later_id = make_job(
        20,
        city="深圳",
        published_at=date(2026, 8, 20),
    )
    earlier_id = make_job(
        2,
        city="东莞",
        published_at=date(2025, 1, 1),
    )
    matcher = ResultMappingMatcher(
        {
            20: make_result(
                later_id,
                score=0,
                matched=[],
                missing=["SQL"],
                reason=MatchReason.NO_SKILL_MATCH,
            ),
            2: make_result(
                earlier_id,
                score=0,
                matched=[],
                missing=[],
                reason=MatchReason.INSUFFICIENT_EVIDENCE,
            ),
        }
    )
    service = make_service(
        FakeJobQuery([later_id, earlier_id]),
        matcher=matcher,
    )
    candidate = CandidateProfile(
        skills=["Python"],
        preferred_cities=["深圳", "东莞"],
    )

    first = service.match_jobs(candidate=candidate, top_k=2)
    second = service.match_jobs(candidate=candidate, top_k=2)

    assert [result.job.id for result in first] == [2, 20]
    assert [result.job.id for result in second] == [2, 20]


def test_zero_evidence_result_is_retained() -> None:
    results = make_service(FakeJobQuery([make_job(1)])).match_jobs(
        candidate=CandidateProfile(skills=["Python"]),
        top_k=1,
    )

    assert len(results) == 1
    assert results[0].match_score == 0
    assert results[0].reason is MatchReason.INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize(
    ("top_k", "expected_count"),
    [
        (1, 1),
        (100, 100),
        (150, 150),
        (200, 151),
    ],
)
def test_positive_top_k_truncates_without_a_service_maximum(
    top_k: int,
    expected_count: int,
) -> None:
    results = make_service(FakeJobQuery(make_jobs(151))).match_jobs(
        candidate=CandidateProfile(skills=["Python"]),
        top_k=top_k,
    )

    assert len(results) == expected_count


@pytest.mark.parametrize("top_k", [0, -1, -100])
def test_nonpositive_top_k_fails_before_query(top_k: int) -> None:
    job_query = FakeJobQuery([make_job(1)])

    with pytest.raises(ValueError, match="top_k"):
        make_service(job_query).match_jobs(
            candidate=CandidateProfile(skills=["Python"]),
            top_k=top_k,
        )

    assert job_query.search_calls == []


@pytest.mark.parametrize("top_k", [True, False, 1.5, "10", None])
def test_noninteger_top_k_fails_before_query(top_k: Any) -> None:
    job_query = FakeJobQuery([make_job(1)])

    with pytest.raises(TypeError, match="top_k"):
        make_service(job_query).match_jobs(
            candidate=CandidateProfile(skills=["Python"]),
            top_k=top_k,
        )

    assert job_query.search_calls == []


def test_extractor_evidence_and_matcher_result_are_preserved() -> None:
    job = make_job(1, title="Python岗位", skills=["SQL"])
    evidence = JobSkillEvidence(skills=["Kubernetes"])
    expected = make_result(
        job,
        score=73,
        matched=["Kubernetes"],
        missing=[],
        reason=MatchReason.PARTIAL_MATCH,
    )
    extractor = StubExtractor(evidence)
    matcher = StubMatcher(expected)
    candidate = CandidateProfile(skills=["Python"])

    results = make_service(
        FakeJobQuery([job]),
        extractor=extractor,
        matcher=matcher,
    ).match_jobs(candidate=candidate, top_k=1)

    assert results[0] is expected
    assert extractor.calls == [job]
    assert matcher.calls == [(candidate, job, evidence)]


def test_job_query_error_propagates_unchanged() -> None:
    error = RuntimeError("query failed")
    job_query = FakeJobQuery(error=error)

    with pytest.raises(RuntimeError) as captured:
        make_service(job_query).match_jobs(
            candidate=CandidateProfile(skills=["Python"]),
            top_k=1,
        )

    assert captured.value is error


def test_extractor_error_propagates_unchanged() -> None:
    error = RuntimeError("extraction failed")
    extractor = RecordingExtractor(error=error)

    with pytest.raises(RuntimeError) as captured:
        make_service(
            FakeJobQuery([make_job(1)]),
            extractor=extractor,
        ).match_jobs(
            candidate=CandidateProfile(skills=["Python"]),
            top_k=1,
        )

    assert captured.value is error


def test_matcher_error_propagates_unchanged() -> None:
    error = RuntimeError("matching failed")
    matcher = RecordingMatcher(error=error)

    with pytest.raises(RuntimeError) as captured:
        make_service(
            FakeJobQuery([make_job(1)]),
            matcher=matcher,
        ).match_jobs(
            candidate=CandidateProfile(skills=["Python"]),
            top_k=1,
        )

    assert captured.value is error


def test_service_does_not_mutate_candidate_or_jobs() -> None:
    candidate = CandidateProfile(
        skills=["Python", "FastAPI"],
        preferred_cities=["深圳"],
    )
    job = make_job(
        1,
        title="Python实习生",
        description="使用FastAPI和SQL。",
        skills=["Python"],
    )
    candidate_before = candidate.model_dump(mode="python")
    job_before = job.model_dump(mode="python")

    make_service(FakeJobQuery([job])).match_jobs(
        candidate=candidate,
        top_k=1,
    )

    assert candidate.model_dump(mode="python") == candidate_before
    assert job.model_dump(mode="python") == job_before
