"""Validated HTTP boundary for rules-first Agent recommendations."""

import os
import re
from datetime import datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

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
from demo.eligibility_client import EligibilityResult, build_eligibility_profile
from demo.recommendation_quality import (
    DirectionFit, RankingSupport, SkillRequirement, TargetDirection, normalize_targets, quality_order, validate_job_quality,
)
from demo.recommendation_scope import DuplicateGroup, RecommendationDataScope, validate_scope_provenance


class RecommendedJob(BaseModel):
    model_config = ConfigDict(extra="ignore")

    job: LibraryJob
    match_score: int = Field(strict=True, ge=0, le=100)
    matched_skills: list[str]
    missing_skills: list[str]
    detected_job_skills: list[str]
    reason: Literal["full_match", "partial_match", "no_skill_match", "insufficient_evidence"]
    eligibility: EligibilityResult
    direction_fit: DirectionFit | None = None
    skill_requirements: list[SkillRequirement] = Field(default_factory=list)
    ranking_support: RankingSupport | None = None

    @model_validator(mode="after")
    def same_job_and_skill_evidence(self):
        if self.job != self.eligibility.job:
            raise ValueError("Skill and condition evidence must use the same job snapshot.")
        if self.job.status == "closed" or self.eligibility.overall == "not_met":
            raise ValueError("Blocked jobs cannot appear among recommendations.")
        matched = {skill.casefold() for skill in self.matched_skills}
        missing = {skill.casefold() for skill in self.missing_skills}
        detected = {skill.casefold() for skill in self.detected_job_skills}
        if matched & missing or matched | missing != detected:
            raise ValueError("Skill evidence must partition matched and missing skills.")
        if any(
            not skill.strip()
            for skill in self.matched_skills + self.missing_skills + self.detected_job_skills
        ):
            raise ValueError("Skill evidence cannot contain blank values.")
        if any((len(values) != len({skill.casefold() for skill in values})) for values in (
            self.matched_skills, self.missing_skills, self.detected_job_skills
        )):
            raise ValueError("Skill evidence must not contain duplicates.")
        return self


class RecommendationCounts(BaseModel):
    evaluated: int = Field(strict=True, ge=0)
    met: int = Field(strict=True, ge=0)
    unknown: int = Field(strict=True, ge=0)
    not_met: int = Field(strict=True, ge=0)
    closed: int = Field(strict=True, ge=0)
    direction_mismatch: int = Field(default=0, strict=True, ge=0)
    returned: int = Field(strict=True, ge=0)


class JobExplanation(BaseModel):
    job_id: int = Field(strict=True, gt=0)
    reasons: list[StrictStr] = Field(min_length=1, max_length=3)

    @field_validator("reasons")
    @classmethod
    def nonblank_reasons(cls, value):
        if any(not reason.strip() for reason in value):
            raise ValueError("Explanation reasons cannot be blank.")
        return [reason.strip() for reason in value]


class AgentRecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    recommendations: list[RecommendedJob]
    excluded: list[EligibilityResult] = Field(max_length=10)
    counts: RecommendationCounts
    limit: int = Field(strict=True, ge=1, le=50)
    assessed_at: datetime
    summary: str = Field(min_length=1)
    model_explanation: str | None = None
    job_explanations: list[JobExplanation] = Field(default_factory=list)
    explanation_status: Literal["generated", "disabled", "unavailable", "failed", "stale", "not_needed"]
    explanation_notice: str
    steps: int | None = Field(default=None, ge=0)
    tool_execution_count: int | None = Field(default=None, ge=0)
    data_scope: RecommendationDataScope | None = None
    duplicate_groups: list[DuplicateGroup] = Field(default_factory=list)
    ranking_version: Literal["direction-core-v1", "direction-core-v2", "direction-evidence-v3", "direction-support-v4"] | None = None
    target_directions: list[TargetDirection] = Field(default_factory=list)
    direction_excluded: list[RecommendedJob] = Field(default_factory=list, max_length=10)

    @field_validator("job_explanations", mode="before")
    @classmethod
    def optional_structured_explanations(cls, value):
        # Optional AI formatting must never discard valid rule-based cards.
        if not isinstance(value, list):
            return []
        try:
            return [JobExplanation.model_validate(item) for item in value]
        except (ValueError, TypeError):
            return []

    @model_validator(mode="after")
    def complete_consistent_response(self):
        counts = self.counts
        if counts.evaluated != counts.met + counts.unknown + counts.not_met + counts.closed + counts.direction_mismatch:
            raise ValueError("Category counts must partition all evaluated jobs.")
        if counts.returned != len(self.recommendations) or counts.returned != min(
            self.limit, counts.met + counts.unknown
        ):
            raise ValueError("Recommendation counts do not match the returned page.")
        recommended_ids = [item.job.id for item in self.recommendations]
        all_jobs = [item.job for item in (*self.recommendations, *self.excluded, *self.direction_excluded)]
        if len({job.id for job in all_jobs}) != len(all_jobs):
            raise ValueError("A job cannot be duplicated or both recommended and excluded.")
        if len(self.excluded) > counts.not_met + counts.closed or any(
            item.overall != "not_met" for item in self.excluded
        ):
            raise ValueError("Excluded examples must have blocking condition results.")
        if (
            sum(item.eligibility.overall == "met" for item in self.recommendations) > counts.met
            or sum(item.eligibility.overall == "unknown" for item in self.recommendations) > counts.unknown
            or sum(item.job.status == "closed" for item in self.excluded) > counts.closed
            or sum(item.job.status != "closed" for item in self.excluded) > counts.not_met
        ):
            raise ValueError("Returned examples exceed the corresponding category totals.")
        if len(self.direction_excluded) > counts.direction_mismatch:
            raise ValueError("Direction exclusions exceed their category total.")
        if self.ranking_version is None:
            if self.target_directions or counts.direction_mismatch or self.direction_excluded or any(
                item.direction_fit is not None or item.skill_requirements or item.ranking_support is not None for item in self.recommendations
            ):
                raise ValueError("Direction-aware results require a ranking version.")
            order = [
                (0 if item.eligibility.overall == "met" else 1,
                 -item.match_score, -len(item.matched_skills), item.job.id)
                for item in self.recommendations
            ]
        else:
            if "target_directions" not in self.model_fields_set:
                raise ValueError("Current rankings must report the target directions used.")
            if len(set(self.target_directions)) != len(self.target_directions):
                raise ValueError("Target directions must be unique.")
            if len(self.direction_excluded) != min(10, counts.direction_mismatch):
                raise ValueError("Direction exclusion examples must match their reported count.")
            if len(self.excluded) != min(10, counts.closed + counts.not_met):
                raise ValueError("Qualification exclusion examples must match their reported count.")
            if not self.target_directions and counts.direction_mismatch:
                raise ValueError("Unrestricted searches cannot exclude jobs by direction.")
            for item in self.recommendations:
                validate_job_quality(item, self.target_directions, excluded=False, version=self.ranking_version)
            for item in self.direction_excluded:
                validate_job_quality(item, self.target_directions, excluded=True, version=self.ranking_version)
            order = [quality_order(item) for item in self.recommendations]
        if order != sorted(order):
            raise ValueError("The response must preserve deterministic recommendation order.")
        validate_scope_provenance(
            self.data_scope, self.duplicate_groups,
            jobs=all_jobs, evaluated=counts.evaluated,
        )
        explanation_ids = [item.job_id for item in self.job_explanations]
        if self.explanation_status != "generated" or explanation_ids != recommended_ids:
            self.job_explanations = []
        if self.explanation_status == "generated" and not (
            self.job_explanations or self.model_explanation and self.model_explanation.strip()
        ):
            self.explanation_status = "failed"
            self.explanation_notice = "AI 补充说明格式不完整，规则推荐结果仍可查看。"
        return self


def build_recommendation_candidate(
    *, skills_text: str, **condition_inputs: Any
) -> dict[str, Any]:
    skills = list(dict.fromkeys(
        skill.strip() for skill in re.split(r"[,，、;；\n]", skills_text) if skill.strip()
    ))
    if not skills:
        raise ValueError("请至少填写一项你具备的技能。")
    if len(skills) > 100 or any(len(skill) > 100 for skill in skills):
        raise ValueError("最多填写 100 项技能，每项不超过 100 个字符。")
    targets = normalize_targets(condition_inputs.pop("target_directions", []))
    return {
        "skills": skills, "conditions": build_eligibility_profile(**condition_inputs),
        "target_directions": targets,
    }


class RecommendationApiClient:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_API_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.strip().rstrip("/")
        if not self._base_url or timeout_seconds <= 0:
            raise ValueError("推荐服务地址或等待时间配置无效。")
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    @classmethod
    def from_env(cls) -> "RecommendationApiClient":
        try:
            timeout = float(os.getenv(API_TIMEOUT_ENV, str(DEFAULT_TIMEOUT_SECONDS)))
        except ValueError as exc:
            raise ValueError("推荐服务等待时间配置无效。") from exc
        return cls(
            base_url=os.getenv(API_BASE_URL_ENV, DEFAULT_API_BASE_URL), timeout_seconds=timeout
        )

    def recommend(
        self, *, candidate: dict[str, Any], limit: int = 10, explain_with_model: bool = True,
        include_samples: bool = False,
    ) -> AgentRecommendationResponse:
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("展示数量应为 1–50 之间的整数。")
        if type(explain_with_model) is not bool:
            raise ValueError("请选择是否需要 AI 补充说明。")
        if type(include_samples) is not bool:
            raise ValueError("请选择是否包含演示数据。")
        targets = normalize_targets(candidate.get("target_directions", []))
        wire_candidate = dict(candidate)
        if targets:
            wire_candidate["target_directions"] = targets
        else:
            # Empty is the current server default and older servers reject this field.
            wire_candidate.pop("target_directions", None)
        try:
            with httpx.Client(
                base_url=self._base_url, timeout=self._timeout_seconds, transport=self._transport
            ) as client:
                response = client.post("/api/agent/recommend", json={
                    "candidate": wire_candidate, "limit": limit, "explain_with_model": explain_with_model,
                    "include_samples": include_samples,
                })
        except httpx.TimeoutException as exc:
            raise BackendTimeoutError(
                "等待推荐超时，尚未取得完整结果。可关闭 AI 补充说明后重新请求；不会自动重试。"
            ) from exc
        except httpx.RequestError as exc:
            raise BackendUnavailableError("暂时无法连接推荐服务，请确认后端已启动。") from exc
        if response.status_code >= 500:
            raise BackendUnavailableError("推荐服务暂时不可用，请稍后重新请求。")
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
            if not isinstance(detail, str) or not detail.strip():
                detail = f"推荐请求未被接受（HTTP {response.status_code}），请检查填写内容。"
            raise BackendRequestError(detail)
        try:
            parsed = AgentRecommendationResponse.model_validate(response.json())
            if parsed.limit != limit:
                raise ValueError("Response limit differs from the requested limit.")
            if parsed.data_scope is not None and parsed.data_scope.include_samples != include_samples:
                raise ValueError("Response data scope differs from the requested sample setting.")
            if targets and parsed.ranking_version is None:
                raise BackendResponseError("推荐服务未返回所选岗位方向的判断，请更新服务后重新获取推荐。")
            if parsed.target_directions != targets:
                raise ValueError("Returned target directions differ from the request.")
            return parsed
        except ValueError as exc:
            raise BackendResponseError(
                "推荐结果不完整，或岗位、条件依据与排序不一致；本次结果未展示，请重新请求。"
            ) from exc
