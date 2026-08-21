"""Tests for the Demo-side response contract."""

import pytest
from pydantic import ValidationError

from demo.contracts import DemoAgentResponse


def test_response_contract_parses_backend_recommendation_shape() -> None:
    response = DemoAgentResponse.model_validate(
        {
            "answer": "已找到岗位。",
            "steps": 2,
            "tool_execution_count": 1,
            "recommendations": [
                {
                    "job": {
                        "title": "数据分析实习生",
                        "company": "星河科技",
                        "city": "上海",
                        "salary": None,
                        "source_url": None,
                        "ignored_backend_field": "ignored",
                    },
                    "match_score": 80,
                    "matched_skills": ["Python"],
                    "missing_skills": [],
                    "reason": "full_match",
                    "ignored_matching_field": [],
                }
            ],
        }
    )

    assert response.recommendations is not None
    assert response.recommendations[0].job.title == (
        "数据分析实习生"
    )
    assert response.recommendations[0].match_score == 80


def test_response_contract_allows_legacy_response_without_recommendations() -> None:
    response = DemoAgentResponse.model_validate(
        {
            "answer": "普通 Agent 回答。",
            "steps": 1,
            "tool_execution_count": 0,
        }
    )

    assert response.recommendations is None


def test_response_contract_rejects_invalid_score() -> None:
    with pytest.raises(ValidationError):
        DemoAgentResponse.model_validate(
            {
                "answer": "错误数据。",
                "steps": 1,
                "tool_execution_count": 1,
                "recommendations": [
                    {
                        "job": {
                            "title": "岗位",
                            "company": "公司",
                            "city": "城市",
                        },
                        "match_score": 101,
                        "matched_skills": [],
                        "missing_skills": [],
                        "reason": "full_match",
                    }
                ],
            }
        )
