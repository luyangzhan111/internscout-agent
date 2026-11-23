"""Typed evidence and three-state decisions, separate from skill scoring."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from app.schemas.job_response import JobRead


Dimension = Literal["graduation_year", "degree", "experience", "city", "internship_duration"]
Degree = Literal["below_associate", "associate", "bachelor", "master", "doctor"]
DecisionStatus = Literal["met", "not_met", "unknown"]
UnknownReason = Literal[
    "candidate_missing", "source_unspecified", "interpretation_uncertain", "requirements_conflict",
]


class EligibilityProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graduation_year: int | None = Field(default=None, ge=2000, le=2100, strict=True)
    degree: Degree | None = None
    degree_status: Literal["enrolled", "completed"] | None = None
    work_experience_months: int | None = Field(default=None, ge=0, le=1200, strict=True)
    # None = not supplied; [] = explicitly no city restriction.
    acceptable_cities: list[StrictStr] | None = Field(default=None, max_length=20)
    internship_months: int | None = Field(default=None, ge=0, le=120, strict=True)

    @field_validator("acceptable_cities")
    @classmethod
    def validate_cities(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cities = list(dict.fromkeys(city.strip() for city in value))
        if any(not city or len(city) > 50 for city in cities):
            raise ValueError("城市不能为空且每项不能超过 50 个字符。")
        return cities


class EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["title", "description", "city"]
    text: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered_span(self):
        if self.end <= self.start or self.end - self.start != len(self.text):
            raise ValueError("Evidence offsets must exactly match the quoted text length")
        return self


class ConditionRule(BaseModel):
    """One recognized clause; uncertain clauses must never become hard filters."""

    model_config = ConfigDict(extra="forbid")
    dimension: Dimension
    kind: Literal["required", "preferred", "unrestricted", "uncertain"]
    operator: Literal["in", "min", "max", "range", "any", "unknown"]
    years: list[int] = Field(default_factory=list)
    degrees: list[Degree] = Field(default_factory=list)
    degree_status: Literal["enrolled", "completed"] | None = None
    # Capability clauses describe one applicant branch, not a shared level gate.
    degree_scope: Literal["applicant", "conditional_capability"] = "applicant"
    degree_exclusive: bool = False
    min_months: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    max_months: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    cities: list[str] = Field(default_factory=list)
    evidence: list[EvidenceSpan] = Field(default_factory=list)
    note: str = ""

    @model_validator(mode="after")
    def degree_metadata_scope(self):
        if self.dimension != "degree" and (self.degree_scope != "applicant" or self.degree_exclusive):
            raise ValueError("Degree scope metadata is only valid for degree rules")
        if self.degree_scope == "conditional_capability" and self.degree_status is not None:
            raise ValueError("A degree-state condition cannot be ignored as capability context")
        return self


class ConditionCheck(BaseModel):
    dimension: Dimension
    status: DecisionStatus
    reason: str
    candidate_value: str
    requirement: str
    evidence: list[EvidenceSpan]
    notes: list[str] = Field(default_factory=list)
    # Older saved results remain readable without guessing why they were unknown.
    unknown_reason: UnknownReason | None = None
    next_step: str = ""

    @model_validator(mode="after")
    def clear_resolved_follow_up(self):
        if self.status != "unknown":
            self.unknown_reason = None
            self.next_step = ""
        return self


class JobEligibilityResult(BaseModel):
    job: JobRead
    overall: DecisionStatus
    reason: str
    checks: list[ConditionCheck]
    blocking_reasons: list[str] = Field(default_factory=list)
    source_fingerprint: str
    rules_version: str


class EligibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: EligibilityProfile
    job_ids: list[int] = Field(min_length=1, max_length=50)

    @field_validator("job_ids", mode="before")
    @classmethod
    def positive_unique_ids(cls, value):
        if not isinstance(value, list):
            return value
        if any(type(item) is not int or item <= 0 for item in value):
            raise ValueError("岗位编号必须为正整数。")
        if len(value) != len(set(value)):
            raise ValueError("岗位编号不能重复。")
        return value


class EligibilityResponse(BaseModel):
    items: list[JobEligibilityResult]
    assessed_at: datetime
