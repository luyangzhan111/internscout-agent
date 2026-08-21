"""Tests for pure Demo presentation transformations."""

from demo.contracts import DemoAgentResponse
from demo.rendering import build_recommendation_views


def test_rendering_formats_recommendation_fields() -> None:
    response = DemoAgentResponse.model_validate(
        {
            "answer": "推荐完成。",
            "steps": 2,
            "tool_execution_count": 1,
            "recommendations": [
                {
                    "job": {
                        "title": "Python后端实习生",
                        "company": "星河科技",
                        "city": "深圳",
                        "salary": "150-200元/天",
                        "source_url": "https://example.com/jobs/1",
                    },
                    "match_score": 50,
                    "matched_skills": ["Python"],
                    "missing_skills": ["FastAPI"],
                    "reason": "partial_match",
                }
            ],
        }
    )

    views = build_recommendation_views(response)

    assert views[0].title == "Python后端实习生"
    assert views[0].score == "50/100"
    assert views[0].matched_skills == "Python"
    assert views[0].missing_skills == "FastAPI"
    assert views[0].reason == "技能部分匹配"


def test_rendering_handles_empty_and_missing_skill_lists() -> None:
    response = DemoAgentResponse.model_validate(
        {
            "answer": "没有匹配岗位。",
            "steps": 1,
            "tool_execution_count": 1,
            "recommendations": [
                {
                    "job": {
                        "title": "岗位",
                        "company": "公司",
                        "city": "城市",
                    },
                    "match_score": 0,
                    "matched_skills": [],
                    "missing_skills": [],
                    "reason": "no_skill_match",
                }
            ],
        }
    )

    views = build_recommendation_views(response)

    assert views[0].matched_skills == "无"
    assert views[0].missing_skills == "无"
    assert views[0].salary == "未提供"
    assert views[0].reason == "没有匹配技能"
