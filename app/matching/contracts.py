"""Validated request and result contracts for deterministic matching."""

from enum import StrEnum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
    model_validator,
)

from app.schemas.job_response import JobRead
from app.services.cleaner import normalize_city
from app.services.skill_vocabulary import normalize_skill


def _normalize_skill_values(
    value: Any,
    *,
    allow_empty: bool,
) -> Any:
    """Strictly validate and canonicalize a supplied skill list."""

    if not isinstance(value, list):
        return value

    normalized_values: list[str] = []

    for skill in value:
        if not isinstance(skill, str):
            return value

        if not skill.strip():
            raise ValueError(
                "Skills cannot contain blank values."
            )

        normalized_values.append(normalize_skill(skill))

    if not allow_empty and not normalized_values:
        raise ValueError(
            "At least one skill is required."
        )

    result: list[str] = []
    seen: set[str] = set()

    for skill in normalized_values:
        identity = skill.casefold()

        if identity in seen:
            continue

        seen.add(identity)
        result.append(skill)

    return result


def _normalize_city_values(value: Any) -> Any:
    """Strictly validate and canonicalize a supplied city list."""

    if not isinstance(value, list):
        return value

    result: list[str] = []
    seen: set[str] = set()

    for city in value:
        if not isinstance(city, str):
            return value

        if not city.strip():
            raise ValueError(
                "Preferred cities cannot contain blank values."
            )

        normalized = normalize_city(city)
        identity = normalized.casefold()

        if identity in seen:
            continue

        seen.add(identity)
        result.append(normalized)

    return result


class CandidateProfile(BaseModel):
    """Request-scoped candidate input for one matching operation."""

    model_config = ConfigDict(extra="forbid")

    skills: list[StrictStr]
    preferred_cities: list[StrictStr] = Field(
        default_factory=list
    )

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_candidate_skills(cls, value: Any) -> Any:
        return _normalize_skill_values(
            value,
            allow_empty=False,
        )

    @field_validator("preferred_cities", mode="before")
    @classmethod
    def normalize_preferred_cities(cls, value: Any) -> Any:
        return _normalize_city_values(value)


class JobSkillEvidence(BaseModel):
    """Canonical skill evidence detected for one job."""

    model_config = ConfigDict(extra="forbid")

    skills: list[StrictStr]

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_detected_skills(cls, value: Any) -> Any:
        return _normalize_skill_values(
            value,
            allow_empty=True,
        )


class MatchReason(StrEnum):
    """Stable reason states for a deterministic match result."""

    FULL_MATCH = "full_match"
    PARTIAL_MATCH = "partial_match"
    NO_SKILL_MATCH = "no_skill_match"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class JobMatchResult(BaseModel):
    """Validated deterministic matching output for one job."""

    model_config = ConfigDict(extra="forbid")

    job: JobRead
    match_score: int = Field(
        strict=True,
        ge=0,
        le=100,
    )
    matched_skills: list[StrictStr]
    missing_skills: list[StrictStr]
    detected_job_skills: list[StrictStr]
    reason: MatchReason

    @field_validator(
        "matched_skills",
        "missing_skills",
        "detected_job_skills",
        mode="before",
    )
    @classmethod
    def normalize_result_skills(cls, value: Any) -> Any:
        return _normalize_skill_values(
            value,
            allow_empty=True,
        )

    @model_validator(mode="after")
    def validate_skill_partition(self) -> "JobMatchResult":
        detected = {
            skill.casefold()
            for skill in self.detected_job_skills
        }
        matched = {
            skill.casefold()
            for skill in self.matched_skills
        }
        missing = {
            skill.casefold()
            for skill in self.missing_skills
        }

        if matched & missing:
            raise ValueError(
                "Matched and missing skills cannot overlap."
            )

        if not matched <= detected:
            raise ValueError(
                "Every matched skill must be detected for the job."
            )

        if not missing <= detected:
            raise ValueError(
                "Every missing skill must be detected for the job."
            )

        if detected != matched | missing:
            raise ValueError(
                "Detected job skills must be partitioned by "
                "matched and missing skills."
            )

        return self
