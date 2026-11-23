"""Independent source-role counterexamples for Stage22 ordering support."""

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.recommendations.quality import evaluate_direction, evaluate_ranking_support
from app.schemas.job_response import JobRead
from demo.recommendation_quality import (
    DirectionFit as PublicDirectionFit,
    RankingSupport as PublicRankingSupport,
    validate_ranking_support,
)


def source(description: str) -> JobRead:
    return JobRead(
        id=1, title="软件工程实习生", company="合成招聘方", city="北京",
        description=description, skills=[], source="manual",
        source_url="https://audit.fixture.test/jobs/1", salary=None,
        published_at=None, created_at=datetime(2026, 11, 18),
    )


@pytest.mark.parametrize("target,description", [
    ("computer_vision", "岗位职责：负责整理图像模型训练相关材料。"),
    ("computer_vision", "岗位职责：协助算法工程师完成图像模型研发相关文档的整理。"),
    ("ai_application", "岗位职责：负责整理RAG系统开发相关宣传材料。"),
    ("backend", "岗位职责：协助后端工程师整理API接口系统设计文档。"),
])
def test_document_or_collaborator_topic_is_not_applicant_development_support(target, description):
    job = source(description)
    fit = evaluate_direction(job, [target])
    assert fit.status == "uncertain"
    before = fit.model_dump()
    support = evaluate_ranking_support(job, [target], fit, [])
    assert support.level == "insufficient"
    assert support.targets == support.matched_target_skills == []
    assert fit.model_dump() == before


def test_actual_model_work_is_not_lost_when_its_results_include_documentation():
    job = source("岗位职责：负责图像深度模型的训练与量化，并整理实验记录。")
    fit = evaluate_direction(job, ["computer_vision"])
    assert fit.status == "uncertain"
    support = evaluate_ranking_support(job, ["computer_vision"], fit, [])
    assert support.level == "target_specific"
    assert support.targets == ["computer_vision"]
    assert support.matched_target_skills == []
    assert all(job.description[span.start:span.end] == span.text for span in support.evidence)


def test_frontend_ranking_quote_must_not_claim_offsets_outside_its_source():
    job = source("岗位职责：负责图像深度模型的训练与量化。")
    support = PublicRankingSupport(
        level="target_specific", targets=["computer_vision"], reason="需核对职责。",
        evidence=[{"field": "description", "start": 0, "end": 10000, "text": job.description}],
    )
    item = SimpleNamespace(
        job=job, ranking_support=support, matched_skills=[],
        direction_fit=PublicDirectionFit(status="uncertain", detected_directions=[],
                                        reason="尚无明确方向依据。", evidence=[], target_checks=[]),
    )
    with pytest.raises(ValueError):
        validate_ranking_support(item, ["computer_vision"], "direction-support-v4")
