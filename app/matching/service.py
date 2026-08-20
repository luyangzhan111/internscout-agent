"""Application orchestration for deterministic candidate/job matching."""

from app.agent.tools.job_query import JobQueryPort
from app.matching.contracts import CandidateProfile, JobMatchResult
from app.matching.matcher import CandidateMatcher
from app.matching.skill_extractor import JobSkillExtractor
from app.schemas.job_response import JobRead


PAGE_SIZE = 100


class JobMatchingService:
    """Match one candidate against all stored, city-eligible jobs."""

    def __init__(
        self,
        *,
        job_query: JobQueryPort,
        skill_extractor: JobSkillExtractor,
        matcher: CandidateMatcher,
    ) -> None:
        self._job_query = job_query
        self._skill_extractor = skill_extractor
        self._matcher = matcher

    def match_jobs(
        self,
        *,
        candidate: CandidateProfile,
        top_k: int,
    ) -> list[JobMatchResult]:
        """Return the strongest globally ranked eligible job matches."""

        self._validate_top_k(top_k)

        jobs = self._collect_unique_jobs()
        preferred_city_ids = {
            city.casefold()
            for city in candidate.preferred_cities
        }
        results: list[JobMatchResult] = []

        for job in jobs:
            if (
                preferred_city_ids
                and job.city.casefold() not in preferred_city_ids
            ):
                continue

            evidence = self._skill_extractor.extract(job)
            results.append(
                self._matcher.match(
                    candidate=candidate,
                    job=job,
                    evidence=evidence,
                )
            )

        results.sort(
            key=lambda result: (
                -result.match_score,
                -len(result.matched_skills),
                result.job.id,
            )
        )

        return results[:top_k]

    def _collect_unique_jobs(self) -> list[JobRead]:
        first_page, total = self._job_query.search_jobs(
            page=1,
            page_size=PAGE_SIZE,
        )
        page_count = (
            total + PAGE_SIZE - 1
        ) // PAGE_SIZE
        collected_jobs = list(first_page)

        for page in range(2, page_count + 1):
            page_jobs, _ = self._job_query.search_jobs(
                page=page,
                page_size=PAGE_SIZE,
            )
            collected_jobs.extend(page_jobs)

        unique_jobs: list[JobRead] = []
        seen_job_ids: set[int] = set()

        for job in collected_jobs:
            if job.id in seen_job_ids:
                continue

            seen_job_ids.add(job.id)
            unique_jobs.append(job)

        return unique_jobs

    @staticmethod
    def _validate_top_k(top_k: int) -> None:
        if type(top_k) is not int:
            raise TypeError("top_k must be an integer.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")
