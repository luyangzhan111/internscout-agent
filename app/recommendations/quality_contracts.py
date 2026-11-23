"""Rule-owned recommendation direction and skill classifications."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, model_validator

from app.eligibility.contracts import EvidenceSpan


TargetDirection = Literal[
    "ai_application", "backend", "computer_vision", "data", "frontend",
    "test_development", "devops", "security",
]
DetectedDirection = Literal[TargetDirection, "other"]
DirectionStatus = Literal["aligned", "uncertain", "unrelated", "not_requested"]
SkillImportance = Literal["core", "bonus", "unclassified"]


class RankingSupport(BaseModel):
    """Source-bound ordering support, independent of a direction decision."""

    model_config = ConfigDict(extra="forbid")
    level: Literal["target_specific", "insufficient", "other_direction", "not_applicable"]
    targets: list[TargetDirection] = Field(default_factory=list)
    matched_target_skills: list[StrictStr] = Field(default_factory=list)
    reason: StrictStr = Field(min_length=1)
    evidence: list[EvidenceSpan] = Field(default_factory=list)

    @model_validator(mode="after")
    def verify_support(self):
        if not self.reason.strip():
            raise ValueError("Ranking support needs a nonempty explanation.")
        if len(self.targets) != len(set(self.targets)):
            raise ValueError("Supported targets must be unique.")
        skills = [skill.casefold() for skill in self.matched_target_skills]
        if len(skills) != len(set(skills)) or any(not skill.strip() for skill in skills):
            raise ValueError("Ranking skills must be nonempty and unique.")
        if any(span.field not in {"title", "description"} for span in self.evidence):
            raise ValueError("Ranking support must quote the job title or description.")
        if self.level == "target_specific":
            if not self.targets or not self.evidence:
                raise ValueError("Target-specific support needs targets and source evidence.")
        elif self.targets or self.matched_target_skills:
            raise ValueError("Only target-specific support may claim targets or matched skills.")
        if self.level == "other_direction" and not self.evidence:
            raise ValueError("Other-direction ordering needs positive source evidence.")
        if self.level == "not_applicable" and self.evidence:
            raise ValueError("An unchanged ordering group cannot claim ordering evidence.")
        return self


class TargetDirectionCheck(BaseModel):
    """Evidence for one requested target, independently of other role clues."""

    model_config = ConfigDict(extra="forbid")
    target: TargetDirection
    status: Literal["aligned", "unrelated", "uncertain"]
    reason: StrictStr = Field(min_length=1)
    evidence: list[EvidenceSpan] = Field(default_factory=list)

    @model_validator(mode="after")
    def verify_check(self):
        if not self.reason.strip():
            raise ValueError("A target direction needs a nonempty reason.")
        if self.status != "uncertain" and not self.evidence:
            raise ValueError("A resolved target direction requires source evidence.")
        if any(span.field not in {"title", "description"} for span in self.evidence):
            raise ValueError("A target direction quote must come from title or description.")
        return self


class DirectionFit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: DirectionStatus
    detected_directions: list[DetectedDirection] = Field(default_factory=list)
    reason: StrictStr = Field(min_length=1)
    evidence: list[EvidenceSpan] = Field(default_factory=list)
    # Empty preserves the pre-v3 response contract. New responses explicitly
    # separate a missing target observation from evidence against that target.
    target_checks: list[TargetDirectionCheck] = Field(default_factory=list)

    @model_validator(mode="after")
    def verify_decision(self):
        if len(self.detected_directions) != len(set(self.detected_directions)):
            raise ValueError("A detected direction must be unique.")
        if any(span.field not in {"title", "description"} for span in self.evidence):
            raise ValueError("A role quote must come from the job title or description.")
        if self.target_checks:
            targets = [check.target for check in self.target_checks]
            if len(targets) != len(set(targets)):
                raise ValueError("Requested target checks must be unique.")
            statuses = [check.status for check in self.target_checks]
            expected = ("aligned" if "aligned" in statuses else
                        "unrelated" if all(status == "unrelated" for status in statuses) else "uncertain")
            if self.status != expected:
                raise ValueError("The direction status must aggregate its requested target checks.")
            for check in self.target_checks:
                if check.status == "aligned" and check.target not in self.detected_directions:
                    raise ValueError("An aligned target must have a detected positive role.")
                if check.status == "unrelated" and check.target in self.detected_directions:
                    raise ValueError("Positive and negative target evidence must remain uncertain.")
                if any(span not in self.evidence for span in check.evidence):
                    raise ValueError("Target evidence must also be present in the source-bound role evidence.")
        elif self.status in {"aligned", "unrelated"}:
            if not self.evidence or not self.detected_directions:
                raise ValueError("A known legacy direction requires a role and a source quote.")
        elif self.detected_directions or (self.status == "not_requested" and self.evidence):
            raise ValueError("An unknown or unrequested legacy direction cannot assert a detected role.")
        return self


class SkillRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skill: StrictStr = Field(min_length=1)
    importance: SkillImportance
    matched: StrictBool
    evidence: list[EvidenceSpan] = Field(default_factory=list)

    @model_validator(mode="after")
    def verify_strength(self):
        if self.importance != "unclassified" and not any(span.field == "description" for span in self.evidence):
            raise ValueError("A core or bonus skill requires a source clause in the description.")
        if any(span.field not in {"title", "description"} for span in self.evidence):
            raise ValueError("A skill quote must come from the job title or description.")
        return self
