"""Ordering support remains separate from qualifications and source truth."""
import copy

import pytest

from app.recommendations.contracts import RecommendationBatch, RecommendationCandidate
from app.recommendations.service import RecommendationService
from app.agent.contracts import FinalAnswerResponse
from app.agent.recommendation_runtime import BoundRecommendationArguments, BoundRecommendationTool, run_recommendation_explanation
from tests.agent.fakes.fake_model_client import FakeModelClient
from demo.explanation_presenter import build_job_reasons
from demo.recommendation_client import AgentRecommendationResponse, JobExplanation
from tests.demo.test_direction_evidence import evidence_payload
from tests.demo.test_explanation_presenter import response
from tests.demo.test_recommendation_page import _field, _recommend, _start
from tests.recommendations.test_service import Query, UNRESTRICTED, make_job


def payload():
    jobs = [make_job(1, title="算法研发工程师", description=UNRESTRICTED + "任职要求：熟悉OpenCV，熟悉Python。"),
            make_job(2, title="后端开发工程师", description=UNRESTRICTED + "工作职责：参与后端服务开发。熟悉Python。"),
            make_job(3, title="工程实习生", description=UNRESTRICTED + "任职要求：熟悉Python。"),
            make_job(4, title="计算机视觉工程师", description=UNRESTRICTED + "任职要求：熟悉Python。"),
            make_job(5, title="公关经理", description=UNRESTRICTED + "负责媒体联系。")]
    candidate = RecommendationCandidate(skills=["Python", "OpenCV"], conditions={"acceptable_cities": []},
                                        target_directions=["computer_vision"])
    batch = RecommendationService(Query(jobs)).recommend(candidate)
    return {**batch.model_dump(mode="json"), "summary": "合成排序支持边界检查。",
            "explanation_status": "disabled", "explanation_notice": "本次没有调用模型。"}


def test_real_pipeline_keeps_all_uncertain_candidates_and_explains_order():
    data = payload()
    for model in (RecommendationBatch, AgentRecommendationResponse):
        result = model.model_validate(data)
        assert [item.job.id for item in result.recommendations] == [4, 1, 3, 2]
        assert [item.ranking_support.level for item in result.recommendations] == [
            "not_applicable", "target_specific", "insufficient", "other_direction"]
        assert [item.direction_fit.status for item in result.recommendations] == ["aligned", "uncertain", "uncertain", "uncertain"]
        supported = result.recommendations[1]
        assert supported.ranking_support.matched_target_skills == ["OpenCV"]
        assert supported.matched_skills == ["Python", "OpenCV"]
        assert supported.detected_job_skills == ["Python", "OpenCV"]
        assert result.counts.direction_mismatch == 1


@pytest.mark.parametrize("model", [RecommendationBatch, AgentRecommendationResponse])
@pytest.mark.parametrize("defect", ["missing", "legacy", "unknown_level", "wrong_target", "duplicate_target",
                                    "duplicate_skill", "unmatched_skill", "bad_quote", "empty_quote", "blank_reason",
                                    "neutral_uncertain", "support_aligned", "wrong_order", "unknown_version"])
def test_both_http_boundaries_reject_invalid_support(model, defect):
    data = payload()
    item = data["recommendations"][1]
    support = item["ranking_support"]
    if defect == "missing": item.pop("ranking_support")
    elif defect == "legacy": data["ranking_version"] = "direction-evidence-v3"
    elif defect == "unknown_level": support["level"] = "strong_fit"
    elif defect == "wrong_target": support["targets"] = ["ai_application"]
    elif defect == "duplicate_target": support["targets"] *= 2
    elif defect == "duplicate_skill": support["matched_target_skills"] *= 2
    elif defect == "unmatched_skill": support["matched_target_skills"] = ["RAG"]
    elif defect == "bad_quote": support["evidence"][0]["text"] = "非当前原文"
    elif defect == "empty_quote": support["evidence"] = []
    elif defect == "blank_reason": support["reason"] = "  "
    elif defect == "neutral_uncertain": item["ranking_support"] = {"level": "not_applicable", "reason": "中性"}
    elif defect == "support_aligned": data["recommendations"][0]["ranking_support"] = copy.deepcopy(support)
    elif defect == "wrong_order": data["recommendations"].reverse()
    elif defect == "unknown_version": data["ranking_version"] = "direction-support-v999"
    with pytest.raises(ValueError):
        model.model_validate(data)


def test_v3_history_keeps_original_order_without_new_support():
    data = evidence_payload()
    # The compact UI fixture omits server-required storage fields.
    for card in [*data["recommendations"], *data["direction_excluded"]]:
        for source in (card["job"], card["eligibility"]["job"]):
            source.update(salary=None, skills=[], published_at=None,
                          created_at=source.get("imported_at", "2026-11-12T01:00:00"))
    for model in (RecommendationBatch, AgentRecommendationResponse):
        result = model.model_validate(data)
        assert result.ranking_version == "direction-evidence-v3"
        assert all(item.ranking_support is None for item in result.recommendations)


def test_model_seed_sees_verified_ranking_support_and_cannot_mutate_it():
    batch = RecommendationBatch.model_validate(payload())
    candidate = RecommendationCandidate(skills=["Python", "OpenCV"], conditions={"acceptable_cities": []},
                                        target_directions=["computer_vision"])
    model = FakeModelClient([FinalAnswerResponse(answer="请继续核对方向和投递条件。")])
    run_recommendation_explanation(model, candidate, batch)
    observed = model.requests[0].tool_executions[0].result.data
    assert observed["recommendations"][1]["ranking_support"] == batch.recommendations[1].ranking_support.model_dump(mode="json")
    tool = BoundRecommendationTool(batch)
    original = tool._run(BoundRecommendationArguments())
    batch.recommendations[1].ranking_support.evidence.clear()
    view = tool._run(BoundRecommendationArguments())
    view["recommendations"][1]["ranking_support"]["evidence"].clear()
    assert tool._run(BoundRecommendationArguments()) == original


def test_page_explains_uncertain_ranking_with_source_without_machine_fields(monkeypatch):
    app, _, requests = _start(monkeypatch, payload())
    _field(app.text_input, "你的技能（至少一项，逗号分隔）").set_value("Python, OpenCV").run()
    _field(app.multiselect, "目标岗位方向（可多选）").set_value(["computer_vision"]).run()
    _recommend(app)
    assert not app.error
    text = "\n".join(item.value for item in app.text)
    assert "排序参考 · 有目标相关线索" in text
    assert "排序参考 · 目标相关证据仍不足" in text
    assert "排序参考 · 已有其他方向线索" in text
    assert "相关匹配技能：OpenCV" in text
    assert "熟悉OpenCV" in text
    assert not any(field in text for field in ("ranking_support", "target_specific", "other_direction"))
    assert len([request for request in requests if request.method == "POST"]) == 1


@pytest.mark.parametrize("field", ["ranking_support", "matched_target_skills", "target_specific", "other_direction", "direction-support-v4"])
def test_new_internal_fields_are_not_shown_as_model_prose(field):
    result = response(ids=(7,), structured=[JobExplanation(job_id=7, reasons=[field, "Python与原文有交集。"])])
    assert build_job_reasons(result) == {7: ["Python与原文有交集。"]}
