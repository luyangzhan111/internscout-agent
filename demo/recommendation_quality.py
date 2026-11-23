"""Public direction and skill evidence for the recommendation HTTP client."""

from fractions import Fraction
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, model_validator

from demo.eligibility_client import EligibilityEvidence

if TYPE_CHECKING:
    from demo.recommendation_client import RecommendedJob


TargetDirection = Literal[
    "ai_application", "backend", "computer_vision", "data",
    "frontend", "test_development", "devops", "security",
]
DIRECTION_LABELS = {
    "ai_application": "AI 应用开发", "backend": "后端开发", "computer_vision": "计算机视觉",
    "data": "数据开发／分析", "frontend": "前端开发", "test_development": "测试开发",
    "devops": "运维／DevOps", "security": "安全研发",
}


class TargetDirectionCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: TargetDirection
    status: Literal["aligned", "unrelated", "uncertain"]
    reason: StrictStr = Field(min_length=1)
    evidence: list[EligibilityEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def supported_decision(self):
        if not self.reason.strip() or self.status != "uncertain" and not self.evidence:
            raise ValueError("A resolved target direction needs a reason and source evidence.")
        if any(span.field not in {"title", "description"} for span in self.evidence):
            raise ValueError("Target direction evidence must come from the role source text.")
        return self


class DirectionFit(BaseModel):
    status: Literal["aligned", "uncertain", "unrelated", "not_requested"]
    detected_directions: list[TargetDirection | Literal["other"]]
    reason: str = Field(min_length=1)
    evidence: list[EligibilityEvidence]
    target_checks: list[TargetDirectionCheck] = Field(default_factory=list, max_length=8)


class SkillRequirement(BaseModel):
    skill: str = Field(min_length=1)
    importance: Literal["core", "bonus", "unclassified"]
    matched: StrictBool
    evidence: list[EligibilityEvidence]


class RankingSupport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: Literal["target_specific", "insufficient", "other_direction", "not_applicable"]
    targets: list[TargetDirection] = Field(default_factory=list)
    matched_target_skills: list[StrictStr] = Field(default_factory=list)
    reason: StrictStr = Field(min_length=1)
    evidence: list[EligibilityEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_support_shape(self):
        if not self.reason.strip():
            raise ValueError("Ranking support needs a readable reason.")
        if len(self.targets) != len(set(self.targets)) or len(self.matched_target_skills) != len({skill.casefold() for skill in self.matched_target_skills}):
            raise ValueError("Ranking support cannot repeat goals or skills.")
        if any(not skill.strip() for skill in self.matched_target_skills):
            raise ValueError("Ranking support cannot contain blank skill names.")
        if self.level == "target_specific":
            if not self.targets or not self.evidence:
                raise ValueError("Target support needs selected goals and source evidence.")
        elif self.targets or self.matched_target_skills:
            raise ValueError("Only target support can assert supported goals or skills.")
        if self.level == "other_direction" and not self.evidence:
            raise ValueError("Other-direction ordering needs a source quote.")
        if self.level == "not_applicable" and self.evidence:
            raise ValueError("A neutral ordering does not assert new evidence.")
        if any(span.field not in {"title", "description"} for span in self.evidence):
            raise ValueError("Ranking evidence must come from this role's title or description.")
        return self


def validate_ranking_support(item: "RecommendedJob", targets: list[TargetDirection], version: str | None) -> None:
    support = item.ranking_support
    if version != "direction-support-v4":
        if support is not None:
            raise ValueError("Ranking support requires its matching v4 version.")
        return
    if support is None:
        raise ValueError("The current version must explain its ranking support.")
    is_uncertain = item.direction_fit.status == "uncertain"
    if (support.level == "not_applicable") == is_uncertain:
        raise ValueError("Only uncertain directions use the support tiers.")
    if support.targets != [target for target in targets if target in support.targets]:
        raise ValueError("Ranking support must preserve the selected target scope and order.")
    if any(check.status == "unrelated" and check.target in support.targets for check in item.direction_fit.target_checks):
        raise ValueError("An explicitly denied target cannot supply positive ranking support.")
    if not {skill.casefold() for skill in support.matched_target_skills}.issubset({skill.casefold() for skill in item.matched_skills}):
        raise ValueError("Supported skills must come from the existing matched skill set.")
    for span in support.evidence:
        if span.end - span.start != len(span.text) or getattr(item.job, span.field)[span.start:span.end] != span.text:
            raise ValueError("Ranking support must quote the current job snapshot.")


def normalize_targets(value: list[str]) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(direction, str) or direction not in DIRECTION_LABELS for direction in value
    ):
        raise ValueError("请选择有效的目标岗位方向，或留空表示不限。")
    return list(dict.fromkeys(value))


def validate_job_quality(
    item: "RecommendedJob", targets: list[TargetDirection], *, excluded: bool,
    version: str | None = None,
) -> None:
    fit = item.direction_fit
    if fit is None or not fit.reason.strip():
        raise ValueError("Direction-aware results require a direction assessment.")
    expected_status = "not_requested"
    if version in {"direction-evidence-v3", "direction-support-v4"}:
        if [check.target for check in fit.target_checks] != targets:
            raise ValueError("Each selected target needs one direction check in the original order.")
        if targets:
            states = [check.status for check in fit.target_checks]
            expected_status = ("aligned" if "aligned" in states else
                               "unrelated" if all(state == "unrelated" for state in states) else "uncertain")
        for check in fit.target_checks:
            if ((check.status == "aligned" and check.target not in fit.detected_directions)
                    or (check.status == "unrelated" and check.target in fit.detected_directions)):
                raise ValueError("Target decisions conflict with the reported positive direction clues.")
            if any(span not in fit.evidence for span in check.evidence):
                raise ValueError("Target source evidence must also be available in the direction evidence.")
    elif fit.target_checks:
        raise ValueError("Target-by-target evidence needs its matching version.")
    elif targets:
        if not fit.detected_directions:
            expected_status = "uncertain"
        else:
            expected_status = "aligned" if set(targets).intersection(fit.detected_directions) else "unrelated"
    if fit.status != expected_status or (fit.status == "unrelated") != excluded:
        raise ValueError("Direction assessment does not match the selected scope or result section.")
    if len(set(fit.detected_directions)) != len(fit.detected_directions):
        raise ValueError("Detected directions must be unique.")
    if fit.status == "not_requested" and (fit.evidence or fit.detected_directions):
        raise ValueError("A job without a direction request cannot claim direction evidence.")
    if fit.status in {"aligned", "unrelated"} and not fit.evidence:
        raise ValueError("A classified job requires direction evidence.")
    validate_ranking_support(item, targets, version)
    if [row.skill for row in item.skill_requirements] != item.detected_job_skills:
        raise ValueError("Skill requirements must correspond to every detected skill in order.")
    matched = {skill.casefold() for skill in item.matched_skills}
    evidence = list(fit.evidence)
    for check in fit.target_checks:
        evidence.extend(check.evidence)
    for row in item.skill_requirements:
        if row.matched != (row.skill.casefold() in matched):
            raise ValueError("Skill requirement coverage differs from the skill match.")
        if row.importance != "unclassified" and not any(span.field == "description" for span in row.evidence):
            raise ValueError("A core or bonus skill requires evidence from the description.")
        evidence.extend(row.evidence)
    for span in evidence:
        if (
            span.field not in {"title", "description"}
            or span.end - span.start != len(span.text)
            or getattr(item.job, span.field)[span.start:span.end] != span.text
        ):
            raise ValueError("Direction or skill evidence differs from this job's snapshot.")


def _coverage(rows: list[SkillRequirement], importance: str) -> Fraction:
    selected = [row for row in rows if row.importance == importance]
    return Fraction(sum(row.matched for row in selected), len(selected)) if selected else Fraction(-1)


def quality_order(item: "RecommendedJob") -> tuple:
    support = getattr(item, "ranking_support", None)
    tier = ({"target_specific": 0, "insufficient": 1, "other_direction": 2}.get(support.level, 0)
            if support is not None and item.direction_fit.status == "uncertain" else 0)
    prefix = (
        int(item.eligibility.overall != "met"),
        int(item.direction_fit.status == "uncertain"),
    )
    rest = (
        -_coverage(item.skill_requirements, "core"),
        -_coverage(item.skill_requirements, "bonus"),
        -item.match_score, -len(item.matched_skills), item.job.id,
    )
    return (*prefix, tier, *rest) if support is not None else (*prefix, *rest)
