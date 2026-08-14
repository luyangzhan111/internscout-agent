from abc import ABC, abstractmethod

from app.schemas.job_response import JobRead


class JobQueryPort(ABC):
    """Agent-facing contract for read-only job queries."""

    @abstractmethod
    def search_jobs(
        self,
        *,
        city: str | None = None,
        company: str | None = None,
        skill: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[JobRead], int]:
        """Return one page of jobs and the total matching count."""

    @abstractmethod
    def get_job_by_id(
        self,
        job_id: int,
    ) -> JobRead | None:
        """Return one job by ID, or None when it does not exist."""