from sqlalchemy.orm import Session

from app.agent.tools.job_query import JobQueryPort
from app.database.repository import (
    get_job_by_id as repository_get_job_by_id,
)
from app.database.repository import (
    query_jobs as repository_query_jobs,
)
from app.schemas.job_response import JobRead


class RepositoryJobQueryAdapter(JobQueryPort):
    """Adapt repository-backed reads to the agent job-query contract."""

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def search_jobs(
        self,
        *,
        city: str | None = None,
        company: str | None = None,
        skill: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[JobRead], int]:
        database_jobs, total = repository_query_jobs(
            self._session,
            city=city,
            company=company,
            skill=skill,
            page=page,
            page_size=page_size,
        )

        jobs = [
            JobRead.model_validate(
                database_job
            )
            for database_job
            in database_jobs
        ]

        return jobs, total

    def get_job_by_id(
        self,
        job_id: int,
    ) -> JobRead | None:
        database_job = repository_get_job_by_id(
            self._session,
            job_id,
        )

        if database_job is None:
            return None

        return JobRead.model_validate(
            database_job
        )