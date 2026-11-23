"""HTTP-only contracts and input handling for application conditions."""

import os
import re
from datetime import datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from demo.client import (
    API_BASE_URL_ENV,
    API_TIMEOUT_ENV,
    DEFAULT_API_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    BackendRequestError,
    BackendResponseError,
    BackendTimeoutError,
    BackendUnavailableError,
)
from demo.data_client import LibraryJob


Dimension = Literal["graduation_year", "degree", "experience", "city", "internship_duration"]
DecisionStatus = Literal["met", "not_met", "unknown"]
DIMENSIONS = ("graduation_year", "degree", "experience", "city", "internship_duration")
DEGREES = ("below_associate", "associate", "bachelor", "master", "doctor")


class EligibilityEvidence(BaseModel):
    field: Literal["title", "description", "city"]
    text: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class EligibilityCheck(BaseModel):
    dimension: Dimension
    status: DecisionStatus
    reason: str
    candidate_value: str
    requirement: str
    evidence: list[EligibilityEvidence]
    notes: list[str] = Field(default_factory=list)
    unknown_reason: Literal[
        "candidate_missing", "source_unspecified", "interpretation_uncertain", "requirements_conflict"
    ] | None = None
    next_step: str = ""

    @model_validator(mode="after")
    def guidance_only_for_unknown_conditions(self):
        if self.status != "unknown" and (self.unknown_reason is not None or self.next_step):
            raise ValueError("Only pending conditions may carry uncertainty guidance.")
        return self


class EligibilityResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    job: LibraryJob
    overall: DecisionStatus
    reason: str
    checks: list[EligibilityCheck]
    blocking_reasons: list[str] = Field(default_factory=list)
    source_fingerprint: str
    rules_version: str

    @model_validator(mode="after")
    def require_complete_checks_and_exact_quotes(self):
        if len(self.checks) != len(DIMENSIONS) or {
            check.dimension for check in self.checks
        } != set(DIMENSIONS):
            raise ValueError("The response must include all five distinct conditions.")
        for check in self.checks:
            for evidence in check.evidence:
                original = getattr(self.job, evidence.field)
                if (
                    evidence.end <= evidence.start
                    or evidence.end - evidence.start != len(evidence.text)
                    or original[evidence.start:evidence.end] != evidence.text
                ):
                    raise ValueError("Quoted evidence does not match the returned job.")
        return self


class EligibilityResponse(BaseModel):
    items: list[EligibilityResult]
    assessed_at: datetime


def _optional_integer(value: str, label: str, minimum: int, maximum: int) -> int | None:
    if not value.strip():
        return None
    if not re.fullmatch(r"[0-9]+", value.strip()):
        raise ValueError(f"{label}请填写整数，或留空表示未提供。")
    parsed = int(value.strip())
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{label}请填写 {minimum}–{maximum} 之间的整数。")
    return parsed


def build_eligibility_profile(
    *,
    graduation_year: str = "",
    degree: str | None = None,
    degree_status: str | None = None,
    work_experience_months: str = "",
    city_mode: str = "unknown",
    cities_text: str = "",
    internship_months: str = "",
) -> dict[str, Any]:
    """Preserve unknown, explicit zero, and unrestricted cities distinctly."""

    if degree is not None and degree not in DEGREES:
        raise ValueError("请选择有效的学历，或保留未填写。")
    if degree_status not in {None, "enrolled", "completed"}:
        raise ValueError("请选择有效的学历状态，或保留未说明。")
    cities: list[str] | None
    if city_mode == "unknown":
        cities = None
    elif city_mode == "unrestricted":
        cities = []
    elif city_mode == "selected":
        cities = list(dict.fromkeys(
            city.strip() for city in re.split(r"[,，、;；\n]", cities_text)
            if city.strip()
        ))
        if not cities:
            raise ValueError("选择指定城市后，请至少填写一个可接受的城市。")
        if len(cities) > 20 or any(len(city) > 50 for city in cities):
            raise ValueError("最多填写 20 个城市，每个城市不超过 50 个字符。")
    else:
        raise ValueError("请选择有效的城市意向。")
    return {
        "graduation_year": _optional_integer(graduation_year, "毕业年份", 2000, 2100),
        "degree": degree,
        "degree_status": degree_status,
        "work_experience_months": _optional_integer(
            work_experience_months, "正式工作经验月数", 0, 1200
        ),
        "acceptable_cities": cities,
        "internship_months": _optional_integer(internship_months, "可实习月数", 0, 120),
    }


def job_snapshot(job: LibraryJob) -> dict[str, Any]:
    """Fields relevant to the meaning and provenance of a displayed decision."""

    return job.model_dump(mode="json", exclude={"last_seen_at", "last_checked_at"})


def results_match_current_jobs(
    response: EligibilityResponse, jobs: list[LibraryJob]
) -> bool:
    expected = {job.id: job_snapshot(job) for job in jobs}
    received = {item.job.id: job_snapshot(item.job) for item in response.items}
    return (
        len(expected) == len(jobs)
        and len(received) == len(response.items)
        and expected == received
    )


class EligibilityApiClient:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_API_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.strip().rstrip("/")
        if not self._base_url or timeout_seconds <= 0:
            raise ValueError("投递条件服务地址或等待时间配置无效。")
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    @classmethod
    def from_env(cls) -> "EligibilityApiClient":
        try:
            timeout = float(os.getenv(API_TIMEOUT_ENV, str(DEFAULT_TIMEOUT_SECONDS)))
        except ValueError as exc:
            raise ValueError("投递条件服务等待时间配置无效。") from exc
        return cls(
            base_url=os.getenv(API_BASE_URL_ENV, DEFAULT_API_BASE_URL),
            timeout_seconds=timeout,
        )

    def evaluate(
        self, *, profile: dict[str, Any], job_ids: list[int]
    ) -> EligibilityResponse:
        if not 1 <= len(job_ids) <= 50 or any(
            type(job_id) is not int or job_id <= 0 for job_id in job_ids
        ) or len(set(job_ids)) != len(job_ids):
            raise ValueError("请选择 1–50 个不重复的有效岗位。")
        try:
            with httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.post(
                    "/api/eligibility/evaluate",
                    json={"profile": profile, "job_ids": job_ids},
                )
        except httpx.TimeoutException as exc:
            raise BackendTimeoutError("投递条件判断等待超时，请稍后重新判断。") from exc
        except httpx.RequestError as exc:
            raise BackendUnavailableError("暂时无法连接投递条件服务，请确认后端已启动。") from exc
        if response.status_code >= 500:
            raise BackendUnavailableError("投递条件服务暂时不可用，请稍后重试。")
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
            if not isinstance(detail, str) or not detail.strip():
                detail = f"投递条件请求未被接受（HTTP {response.status_code}），请检查输入或刷新岗位。"
            raise BackendRequestError(detail)
        try:
            result = EligibilityResponse.model_validate(response.json())
            received_ids = [item.job.id for item in result.items]
            if len(received_ids) != len(job_ids) or set(received_ids) != set(job_ids):
                raise ValueError("Response jobs differ from requested jobs.")
            return result
        except ValueError as exc:
            raise BackendResponseError("判断结果不完整或原文依据不一致，请刷新岗位后重试。") from exc
