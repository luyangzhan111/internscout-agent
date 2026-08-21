"""Pure presentation transformations for the Streamlit Demo."""

from dataclasses import dataclass

from demo.contracts import DemoAgentResponse, DemoRecommendation


_REASON_LABELS = {
    "full_match": "技能完全匹配",
    "partial_match": "技能部分匹配",
    "no_skill_match": "没有匹配技能",
    "insufficient_evidence": "岗位技能证据不足",
}


@dataclass(frozen=True)
class RecommendationView:
    """Display-ready values for one recommendation card."""

    title: str
    company: str
    city: str
    salary: str
    score: str
    matched_skills: str
    missing_skills: str
    reason: str
    source_url: str | None


def build_recommendation_views(
    response: DemoAgentResponse,
) -> list[RecommendationView]:
    """Convert API recommendations into display-only view data."""

    if response.recommendations is None:
        return []

    return [
        _build_recommendation_view(recommendation)
        for recommendation in response.recommendations
    ]


def _build_recommendation_view(
    recommendation: DemoRecommendation,
) -> RecommendationView:
    job = recommendation.job

    return RecommendationView(
        title=job.title,
        company=job.company,
        city=job.city,
        salary=job.salary or "未提供",
        score=f"{recommendation.match_score}/100",
        matched_skills=_format_skills(
            recommendation.matched_skills
        ),
        missing_skills=_format_skills(
            recommendation.missing_skills
        ),
        reason=_REASON_LABELS.get(
            recommendation.reason,
            recommendation.reason,
        ),
        source_url=job.source_url,
    )


def _format_skills(skills: list[str]) -> str:
    """Format an empty or non-empty skill list for display."""

    return "、".join(skills) if skills else "无"
