"""Independent server/client checks for the v3 target evidence boundary."""

import copy

import pytest

from app.agent.recommendation_runtime import BoundRecommendationArguments, BoundRecommendationTool
from app.recommendations.contracts import RecommendationBatch, RecommendationCandidate
from app.recommendations.service import RecommendationService
from demo.recommendation_client import AgentRecommendationResponse
from tests.recommendations.test_service import Query, UNRESTRICTED, make_job


def valid_batch():
    jobs = [
        make_job(1, title="AI应用开发工程师", description=UNRESTRICTED + "负责Agent应用开发；熟悉Python。"),
        make_job(2, title="后端开发工程师", description=UNRESTRICTED + "参与后端服务开发；熟悉Python。"),
        make_job(3, title="公关经理", description=UNRESTRICTED + "负责媒体关系和品牌传播。"),
    ]
    candidate = RecommendationCandidate(skills=["Python"], conditions={"acceptable_cities": []},
                                         target_directions=["ai_application", "computer_vision"])
    return RecommendationService(Query(jobs)).recommend(candidate)


def wire_payload():
    return {**valid_batch().model_dump(mode="json"), "summary": "合成契约检查",
            "explanation_status": "disabled", "explanation_notice": "本次未调用模型。"}


def test_server_and_client_keep_partial_target_knowledge_and_separate_clear_exclusion():
    payload = wire_payload()
    for response in (RecommendationBatch.model_validate(payload), AgentRecommendationResponse.model_validate(payload)):
        assert response.ranking_version == "direction-support-v4"
        assert [item.job.id for item in response.recommendations] == [1, 2]
        assert response.counts.direction_mismatch == 1
        known, unknown = (item.direction_fit for item in response.recommendations)
        assert known.status == "aligned"
        assert [check.status for check in known.target_checks] == ["aligned", "uncertain"]
        assert unknown.status == "uncertain"
        assert unknown.detected_directions == ["backend"]
        assert [check.status for check in unknown.target_checks] == ["uncertain", "uncertain"]
        assert all(check.status == "unrelated" for check in response.direction_excluded[0].direction_fit.target_checks)


@pytest.mark.parametrize("defect", [
    "missing", "order", "duplicate", "wrong_scope", "aggregate", "blank_reason", "no_quote",
    "bad_snapshot", "parent_quote_missing", "positive_conflict", "uncertain_excluded", "unrelated_recommended",
    "v1_with_checks", "v2_with_checks", "unknown_version", "empty_scope_with_checks",
])
@pytest.mark.parametrize("model", [RecommendationBatch, AgentRecommendationResponse])
def test_both_http_boundaries_reject_invalid_target_evidence(defect, model):
    payload = wire_payload()
    fit = payload["recommendations"][0]["direction_fit"]
    check = fit["target_checks"][0]
    if defect == "missing": fit["target_checks"].pop()
    elif defect == "order": fit["target_checks"].reverse()
    elif defect == "duplicate": fit["target_checks"].append(copy.deepcopy(check))
    elif defect == "wrong_scope": fit["target_checks"][1]["target"] = "frontend"
    elif defect == "aggregate": fit["status"] = "uncertain"
    elif defect == "blank_reason": check["reason"] = "  "
    elif defect == "no_quote": check["evidence"] = []
    elif defect == "bad_snapshot":
        card = payload["recommendations"][0]
        card["job"]["title"] = "来源职位名称已变化"
        card["eligibility"]["job"] = copy.deepcopy(card["job"])
    elif defect == "parent_quote_missing": fit["evidence"] = []
    elif defect == "positive_conflict":
        check["status"] = "unrelated"
        fit["status"] = "uncertain"
    elif defect == "uncertain_excluded":
        excluded = payload["direction_excluded"][0]["direction_fit"]
        excluded["status"] = "uncertain"
        for entry in excluded["target_checks"]: entry["status"] = "uncertain"
    elif defect == "unrelated_recommended":
        unknown = payload["recommendations"][1]["direction_fit"]
        unknown["status"] = "unrelated"
        for entry in unknown["target_checks"]:
            entry["status"] = "unrelated"
            entry["evidence"] = copy.deepcopy(unknown["evidence"])
    elif defect == "v1_with_checks": payload["ranking_version"] = "direction-core-v1"
    elif defect == "v2_with_checks": payload["ranking_version"] = "direction-core-v2"
    elif defect == "unknown_version": payload["ranking_version"] = "direction-evidence-v999"
    elif defect == "empty_scope_with_checks": payload["target_directions"] = []
    with pytest.raises(ValueError):
        model.model_validate(payload)


def test_model_tool_observations_cannot_mutate_direction_snapshot():
    batch = valid_batch()
    tool = BoundRecommendationTool(batch)
    original = tool._run(BoundRecommendationArguments())
    batch.recommendations[0].direction_fit.target_checks.clear()
    observed = tool._run(BoundRecommendationArguments())
    assert observed == original
    observed["recommendations"][0]["direction_fit"]["target_checks"][0]["evidence"].clear()
    assert tool._run(BoundRecommendationArguments()) == original
