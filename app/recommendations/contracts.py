"""Server-owned recommendation contracts, independent of model arguments."""

from datetime import datetime
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from app.eligibility.contracts import EligibilityProfile, JobEligibilityResult
from app.matching.contracts import CandidateProfile, JobMatchResult
from app.recommendations.quality_contracts import DirectionFit, RankingSupport, SkillRequirement, TargetDirection


class RecommendationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skills: list[StrictStr] = Field(min_length=1, max_length=100)
    conditions: EligibilityProfile = Field(default_factory=EligibilityProfile)
    target_directions: list[TargetDirection] = Field(default_factory=list, strict=True)

    @field_validator("target_directions")
    @classmethod
    def distinct_directions(cls, value):
        return list(dict.fromkeys(value))

    @field_validator("skills")
    @classmethod
    def normalized_skills(cls, value):
        if any(len(item) > 100 for item in value):
            raise ValueError("每项技能不能超过 100 个字符。")
        return CandidateProfile(skills=value).skills


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate: RecommendationCandidate
    limit: int = Field(default=10, ge=1, le=50, strict=True)
    explain_with_model: bool = Field(default=True, strict=True)
    include_samples: bool = Field(default=False, strict=True)


class EligibleRecommendation(JobMatchResult):
    eligibility: JobEligibilityResult
    direction_fit: DirectionFit | None = None
    skill_requirements: list[SkillRequirement] = Field(default_factory=list)
    ranking_support: RankingSupport | None = None

    @model_validator(mode="after")
    def same_snapshot(self):
        if self.job != self.eligibility.job:
            raise ValueError("Skill and eligibility results must use the same job snapshot.")
        if self.direction_fit is None:
            if self.skill_requirements or self.ranking_support is not None:
                raise ValueError("Skill classifications require the matching direction assessment.")
            return self
        if [entry.skill for entry in self.skill_requirements] != self.detected_job_skills:
            raise ValueError("Skill classifications must use all detected skill names in their original order.")
        matched = {skill.casefold() for skill in self.matched_skills}
        spans = list(self.direction_fit.evidence)
        for check in self.direction_fit.target_checks:
            spans.extend(check.evidence)
        if self.ranking_support is not None:
            from app.recommendations.quality import _skill_pattern
            spans.extend(self.ranking_support.evidence)
            if not {skill.casefold() for skill in self.ranking_support.matched_target_skills}.issubset(matched):
                raise ValueError("Ranking support must use the existing matched skill set.")
            if any(not any(_skill_pattern(skill).search(span.text) for span in self.ranking_support.evidence)
                   for skill in self.ranking_support.matched_target_skills):
                raise ValueError("Every supported skill needs a quoted source mention.")
        for entry in self.skill_requirements:
            if entry.matched != (entry.skill.casefold() in matched):
                raise ValueError("Skill classifications must agree with the existing skill match.")
            spans.extend(entry.evidence)
        for span in spans:
            if span.field not in {"title", "description"} or getattr(self.job, span.field)[span.start:span.end] != span.text:
                raise ValueError("Direction and skill evidence must quote this job snapshot exactly.")
        return self


class RecommendationCounts(BaseModel):
    evaluated: int = Field(ge=0)
    met: int = Field(ge=0)
    unknown: int = Field(ge=0)
    not_met: int = Field(ge=0)
    closed: int = Field(ge=0)
    direction_mismatch: int = Field(default=0, ge=0, strict=True)
    returned: int = Field(ge=0)

    @model_validator(mode="after")
    def consistent_totals(self):
        if self.evaluated != self.met + self.unknown + self.not_met + self.closed + self.direction_mismatch:
            raise ValueError("Recommendation category counts must partition all jobs.")
        if self.returned > self.met + self.unknown:
            raise ValueError("Returned count cannot exceed eligible and unknown jobs.")
        return self


class RecommendationDataScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total_records: int = Field(ge=0, strict=True)
    sample_records_excluded: int = Field(ge=0, strict=True)
    duplicate_records_collapsed: int = Field(ge=0, strict=True)
    include_samples: bool = Field(strict=True)

    @model_validator(mode="after")
    def valid_isolation(self):
        if self.include_samples and self.sample_records_excluded:
            raise ValueError("Including samples cannot also count them as excluded.")
        return self


class SourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: int = Field(gt=0, strict=True)
    source: StrictStr = Field(min_length=1)
    source_url: StrictStr = Field(min_length=1)
    status: Literal["active", "closed", "unknown"]
    last_checked_at: datetime | None = None
    updated_at: datetime | None = None
    title: StrictStr = Field(min_length=1)
    company: StrictStr = Field(min_length=1)


class DuplicateGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    primary_job_id: int = Field(gt=0, strict=True)
    sources: list[SourceRecord] = Field(min_length=2)
    has_conflict: bool = Field(strict=True)
    selection_reason: StrictStr = Field(min_length=1)

    @model_validator(mode="after")
    def valid_members(self):
        from app.recommendations.identity import canonical_identity
        ids = [source.job_id for source in self.sources]
        if ids != sorted(set(ids)) or self.primary_job_id not in ids:
            raise ValueError("Duplicate sources must have stable unique IDs including their primary.")
        keys = {canonical_identity(source.source_url, source.company, source.title) for source in self.sources}
        if None in keys or len(keys) != 1:
            raise ValueError("Duplicate sources must share a valid canonical URL, company, and title.")
        if len({source.status for source in self.sources}) > 1 and not self.has_conflict:
            raise ValueError("Conflicting source statuses must be disclosed.")
        if not self.selection_reason.strip():
            raise ValueError("A primary-source selection reason is required.")
        return self


class RecommendationBatch(BaseModel):
    recommendations: list[EligibleRecommendation]
    # Bounded rejected examples carry actual five-condition results and quotes.
    excluded: list[JobEligibilityResult]
    counts: RecommendationCounts
    limit: int = Field(ge=1, le=50)
    assessed_at: datetime
    # None means an older result did not report isolation/deduplication scope.
    data_scope: RecommendationDataScope | None = None
    duplicate_groups: list[DuplicateGroup] = Field(default_factory=list)
    target_directions: list[TargetDirection] = Field(default_factory=list, strict=True)
    ranking_version: Literal["direction-core-v1", "direction-core-v2", "direction-evidence-v3", "direction-support-v4"] | None = None
    direction_excluded: list[EligibleRecommendation] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def consistent_quality_results(self):
        if self.ranking_version is None:
            if self.target_directions or self.direction_excluded or self.counts.direction_mismatch or any(
                item.direction_fit is not None or item.skill_requirements or item.ranking_support is not None for item in self.recommendations
            ):
                raise ValueError("Target filtering requires a known ranking version.")
            return self
        from app.recommendations.quality import evaluate_ranking_support, quality_rank_key

        targets = set(self.target_directions)
        if len(targets) != len(self.target_directions):
            raise ValueError("The echoed target directions must be unique.")
        if len(self.recommendations) != self.counts.returned or self.counts.returned != min(
            self.limit, self.counts.met + self.counts.unknown
        ):
            raise ValueError("Returned counts must agree with the current limit and recommendations.")
        if len(self.direction_excluded) != min(10, self.counts.direction_mismatch):
            raise ValueError("Direction exclusions must account for the bounded direction mismatch examples.")
        if len(self.excluded) != min(10, self.counts.closed + self.counts.not_met):
            raise ValueError("Qualification exclusion examples must match the reported categories.")
        for item in [*self.recommendations, *self.direction_excluded]:
            fit = item.direction_fit
            if fit is None or (fit.status == "not_requested") != (not targets):
                raise ValueError("Every current card must reflect the selected target directions.")
            if self.ranking_version in {"direction-evidence-v3", "direction-support-v4"}:
                if [check.target for check in fit.target_checks] != self.target_directions:
                    raise ValueError("Per-target direction checks must preserve the requested scope and order.")
            elif fit.target_checks:
                raise ValueError("Per-target direction evidence requires the corresponding v3 version.")
            if self.ranking_version == "direction-support-v4":
                if item.ranking_support is None or item.ranking_support != evaluate_ranking_support(
                    item.job, self.target_directions, fit, item.matched_skills,
                ):
                    raise ValueError("Ranking support must reflect the current selected targets and source snapshot.")
            elif item.ranking_support is not None:
                raise ValueError("Ranking support requires its corresponding v4 version.")
            overlap = targets.intersection(fit.detected_directions)
            if (fit.status == "aligned" and not overlap) or (fit.status == "unrelated" and overlap):
                raise ValueError("Direction status is inconsistent with the selected targets.")
            if item.job.status == "closed" or item.eligibility.overall == "not_met":
                raise ValueError("A qualification block cannot be counted as a direction or recommendation.")
        if any(item.direction_fit.status == "unrelated" for item in self.recommendations):
            raise ValueError("An unrelated job must not consume a recommendation slot.")
        if any(item.direction_fit.status != "unrelated" for item in self.direction_excluded):
            raise ValueError("Only clearly unrelated jobs may be excluded for direction.")
        if self.recommendations != sorted(self.recommendations, key=quality_rank_key):
            raise ValueError("Current recommendations must follow the authoritative ranking.")
        if any(item.overall != "not_met" for item in self.excluded):
            raise ValueError("Qualification exclusions require a blocking eligibility result.")
        if (
            sum(item.eligibility.overall == "met" for item in self.recommendations) > self.counts.met
            or sum(item.eligibility.overall == "unknown" for item in self.recommendations) > self.counts.unknown
            or sum(item.job.status == "closed" for item in self.excluded) > self.counts.closed
            or sum(item.job.status != "closed" for item in self.excluded) > self.counts.not_met
        ):
            raise ValueError("Displayed jobs must fit within each reported category.")
        return self

    @model_validator(mode="after")
    def consistent_source_scope(self):
        from app.recommendations.identity import is_sample_source
        if self.data_scope is None:
            if self.duplicate_groups:
                raise ValueError("Duplicate groups require reported data scope.")
            return self
        scope = self.data_scope
        if scope.total_records != scope.sample_records_excluded + scope.duplicate_records_collapsed + self.counts.evaluated:
            raise ValueError("Data scope must account for every source record exactly once.")
        displayed = [item.job for item in (*self.recommendations, *self.excluded, *self.direction_excluded)]
        visible = {job.id: job for job in displayed}
        if len(visible) != len(displayed):
            raise ValueError("A primary job cannot occupy multiple displayed positions.")
        seen_members: set[int] = set()
        shown_collapsed = 0
        for group in self.duplicate_groups:
            if group.primary_job_id not in visible:
                raise ValueError("Only displayed recommendations/exclusions may report duplicate groups.")
            for source in group.sources:
                if source.job_id in seen_members or (source.job_id in visible and source.job_id != group.primary_job_id):
                    raise ValueError("A source cannot appear in multiple groups or as another displayed job.")
                seen_members.add(source.job_id)
                if not scope.include_samples and is_sample_source(source.source, source.source_url):
                    raise ValueError("Sample sources must be isolated before grouping.")
            primary = next(source for source in group.sources if source.job_id == group.primary_job_id)
            job = visible[group.primary_job_id]
            if any(getattr(primary, name) != getattr(job, name) for name in (
                "source", "source_url", "status", "last_checked_at", "updated_at", "title", "company"
            )):
                raise ValueError("Primary metadata must match the displayed job snapshot.")
            shown_collapsed += len(group.sources) - 1
        if shown_collapsed > scope.duplicate_records_collapsed or (
            len(displayed) == self.counts.evaluated and shown_collapsed != scope.duplicate_records_collapsed
        ):
            raise ValueError("Displayed duplicate groups disagree with the full data scope.")
        if not scope.include_samples and any(is_sample_source(job.source, job.source_url) for job in displayed):
            raise ValueError("Sample jobs cannot appear when sample inclusion is disabled.")
        return self


class JobExplanation(BaseModel):
    """Brief model-written prose attached only to one recommended job."""

    model_config = ConfigDict(extra="forbid")

    job_id: int = Field(gt=0, strict=True)
    reasons: list[StrictStr] = Field(min_length=1, max_length=3)

    @field_validator("reasons")
    @classmethod
    def plain_reasons(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            text = " ".join(value.split())
            if not text or len(text) > 200:
                raise ValueError("每条推荐理由应为 1 至 200 个字符的简短文本。")
            if (
                "*" in text or "`" in text or "__" in text
                or re.search(r"^(?:#{1,6}\s|[-+•]\s|\d+[.、)]\s)|\[[^\]]+\]\([^)]+\)", text)
            ):
                raise ValueError("推荐理由必须是无 Markdown 标记的纯文本。")
            if re.search(
                r"(?<![A-Za-z0-9_])(?:not_met|unknown|met|"
                r"full_match|partial_match|no_skill_match|insufficient_evidence|source_fingerprint|rules_version|"
                r"match_score|job_id|degree_status|work_experience_months|internship_months|acceptable_cities|"
                r"unknown_reason|next_step|candidate_missing|source_unspecified|interpretation_uncertain|requirements_conflict|"
                r"data_scope|include_samples|duplicate_groups|total_records|sample_records_excluded|duplicate_records_collapsed|"
                r"primary_job_id|has_conflict|selection_reason|is_sample|last_checked_at|updated_at|"
                r"target_directions|detected_directions|direction_fit|skill_requirements|direction_excluded|"
                r"direction_mismatch|ranking_version|direction-core-v\d+|direction-evidence-v\d+|direction-support-v\d+|target_checks|"
                r"ranking_support|matched_target_skills|target_specific|other_direction|not_applicable|not_requested|unrelated|uncertain|aligned|"
                r"unclassified|bonus|core(?!\s+ml(?![a-z0-9_]))|"
                r"graduation_year|tool_execution_count|assessed_at|overall|active|closed)(?![A-Za-z0-9_])", text, re.I,
            ):
                raise ValueError("推荐理由不能包含内部字段或技术状态码。")
            cleaned.append(text)
        return cleaned


class AgentRecommendationResponse(RecommendationBatch):
    summary: str
    model_explanation: str | None = None
    job_explanations: list[JobExplanation] = Field(default_factory=list)
    explanation_status: Literal["generated", "disabled", "unavailable", "failed", "stale", "not_needed"]
    explanation_notice: str
    # Failed runs may not return a trace; unknown is not zero model calls.
    steps: int | None = Field(default=None, ge=0)
    tool_execution_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def explanations_match_recommendations(self):
        if self.job_explanations:
            if self.explanation_status != "generated":
                raise ValueError("Only current generated prose can provide per-job reasons.")
            if [item.job_id for item in self.job_explanations] != [item.job.id for item in self.recommendations]:
                raise ValueError("Per-job reasons must exactly follow the current recommendation order.")
        return self
