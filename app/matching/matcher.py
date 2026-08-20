"""Deterministic candidate-to-job skill matching."""

from app.matching.contracts import (
    CandidateProfile,
    JobMatchResult,
    JobSkillEvidence,
    MatchReason,
)
from app.schemas.job_response import JobRead


class CandidateMatcher:
    """Calculate deterministic skill compatibility for one job."""

    def match(
        self,
        *,
        candidate: CandidateProfile,
        job: JobRead,
        evidence: JobSkillEvidence,
    ) -> JobMatchResult:
        """Return a new match result using supplied skill evidence only."""

        candidate_skill_identities = {
            skill.casefold() for skill in candidate.skills
        }
        matched_skills: list[str] = []
        missing_skills: list[str] = []

        for skill in evidence.skills:
            if skill.casefold() in candidate_skill_identities:
                matched_skills.append(skill)
            else:
                missing_skills.append(skill)

        detected_count = len(evidence.skills)
        matched_count = len(matched_skills)

        if detected_count == 0:
            match_score = 0
            reason = MatchReason.INSUFFICIENT_EVIDENCE
        else:
            match_score = (
                200 * matched_count + detected_count
            ) // (2 * detected_count)

            if matched_count == detected_count:
                reason = MatchReason.FULL_MATCH
            elif matched_count == 0:
                reason = MatchReason.NO_SKILL_MATCH
            else:
                reason = MatchReason.PARTIAL_MATCH

        return JobMatchResult(
            job=job,
            match_score=match_score,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            detected_job_skills=evidence.skills,
            reason=reason,
        )
