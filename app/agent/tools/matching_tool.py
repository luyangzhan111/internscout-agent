"""Provider-neutral Agent Tool adapter for deterministic job matching."""

from typing import Any

from pydantic import Field

from app.agent.tools.base import BaseTool
from app.matching.contracts import CandidateProfile
from app.matching.service import JobMatchingService


class MatchJobsArguments(CandidateProfile):
    """Validated candidate input accepted by the match_jobs tool."""

    top_k: int = Field(
        default=5,
        strict=True,
    )


class MatchJobsTool(
    BaseTool[MatchJobsArguments]
):
    """Read-only adapter exposing deterministic job matching to the Agent."""

    name = "match_jobs"
    description = (
        "Match a candidate's skills and preferred cities "
        "against stored jobs and return ranked results."
    )
    args_schema = MatchJobsArguments

    def __init__(
        self,
        matching_service: JobMatchingService,
    ) -> None:
        self._matching_service = matching_service

    def _run(
        self,
        arguments: MatchJobsArguments,
    ) -> list[dict[str, Any]]:
        candidate = CandidateProfile(
            skills=arguments.skills,
            preferred_cities=arguments.preferred_cities,
        )
        results = self._matching_service.match_jobs(
            candidate=candidate,
            top_k=arguments.top_k,
        )

        return [
            result.model_dump(mode="json")
            for result in results
        ]
