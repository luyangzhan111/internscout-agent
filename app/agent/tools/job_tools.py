from typing import Any

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)
from sqlalchemy.orm import Session

from app.agent.tools.base import BaseTool
from app.database.repository import (
    get_job_by_id,
    query_jobs,
)
from app.schemas.job_response import (
    JobListResponse,
    JobRead,
)


class SearchJobsArguments(BaseModel):
    """Validated arguments accepted by the search_jobs tool."""

    city: str | None = Field(
        default=None,
        max_length=50,
    )
    company: str | None = Field(
        default=None,
        max_length=100,
    )
    skill: str | None = Field(
        default=None,
        max_length=100,
    )
    page: int = Field(
        default=1,
        ge=1,
    )
    page_size: int = Field(
        default=10,
        ge=1,
        le=100,
    )

    @field_validator(
        "city",
        "company",
        "skill",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: Any,
    ) -> Any:
        """Collapse whitespace and reject blank text filters."""

        if value is None:
            return None

        if not isinstance(
            value,
            str,
        ):
            return value

        normalized = " ".join(
            value.split()
        )

        if not normalized:
            raise ValueError(
                "Text filters cannot contain only "
                "whitespace."
            )

        return normalized


class GetJobDetailArguments(BaseModel):
    """Validated arguments accepted by get_job_detail."""

    job_id: int = Field(
        ge=1,
    )


class SearchJobsTool(
    BaseTool[SearchJobsArguments]
):
    """Read-only tool for querying stored jobs."""

    name = "search_jobs"
    description = (
        "Search stored internship jobs using optional "
        "exact filters for city, company, and skill, "
        "with pagination."
    )
    args_schema = SearchJobsArguments

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def _run(
        self,
        arguments: SearchJobsArguments,
    ) -> dict[str, Any]:
        database_jobs, total = query_jobs(
            self._session,
            city=arguments.city,
            company=arguments.company,
            skill=arguments.skill,
            page=arguments.page,
            page_size=arguments.page_size,
        )

        response_items = [
            JobRead.model_validate(
                database_job
            )
            for database_job
            in database_jobs
        ]

        pages = (
            (
                total
                + arguments.page_size
                - 1
            )
            // arguments.page_size
            if total > 0
            else 0
        )

        response = JobListResponse(
            items=response_items,
            total=total,
            page=arguments.page,
            page_size=arguments.page_size,
            pages=pages,
        )

        return response.model_dump(
            mode="json"
        )


class GetJobDetailTool(
    BaseTool[GetJobDetailArguments]
):
    """Read-only tool for retrieving one stored job."""

    name = "get_job_detail"
    description = (
        "Retrieve the stored details of one job using "
        "its database ID."
    )
    args_schema = GetJobDetailArguments

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def _run(
        self,
        arguments: GetJobDetailArguments,
    ) -> dict[str, Any] | None:
        database_job = get_job_by_id(
            self._session,
            arguments.job_id,
        )

        if database_job is None:
            return None

        job = JobRead.model_validate(
            database_job
        )

        return job.model_dump(
            mode="json"
        )