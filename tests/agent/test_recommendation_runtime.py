"""Server-owned recommendation observations cannot be rewritten by a model."""

from datetime import datetime, timezone
import json

import pytest

from app.agent.contracts import FinalAnswerResponse, ToolCall, ToolCallResponse, ToolExecution, ToolResult
from app.agent.model_client import ModelClient
from app.agent.exceptions import AgentError
from app.agent.orchestrator import AgentOrchestrator
from app.agent.recommendation_runtime import BoundRecommendationTool, run_recommendation_explanation
from app.agent.tools.registry import ToolRegistry
from app.eligibility.contracts import EligibilityProfile
from app.eligibility.evaluator import evaluate_eligibility
from app.recommendations.contracts import EligibleRecommendation, RecommendationBatch, RecommendationCandidate, RecommendationCounts
from app.schemas.job_response import JobRead
from tests.agent.fakes.fake_model_client import FakeModelClient


def fixture():
    candidate = RecommendationCandidate(skills=["Python"], conditions=EligibilityProfile(
        graduation_year=2027, degree="bachelor", degree_status="completed",
        work_experience_months=0, acceptable_cities=["深圳"], internship_months=6,
    ))
    job = JobRead(id=1, title="后端实习生", company="Example", city="深圳", salary=None,
                  description="2027届；本科及以上；工作经验不限；工作地点深圳；实习至少6个月。\n" + "UNRELATED_DETAIL " * 500,
                  skills=["Python"], source="manual", source_url="https://jobs.fixture.test/jobs/1",
                  status="active", published_at=None, created_at=datetime(2026, 1, 1))
    eligible = evaluate_eligibility(job, candidate.conditions)
    recommendation = EligibleRecommendation(job=job, match_score=100,
        matched_skills=["Python"], missing_skills=[], detected_job_skills=["Python"],
        reason="full_match", eligibility=eligible)
    closed = job.model_copy(update={"id": 2, "status": "closed"}, deep=True)
    batch = RecommendationBatch(recommendations=[recommendation],
        excluded=[evaluate_eligibility(closed, candidate.conditions)],
        counts=RecommendationCounts(evaluated=2, met=1, unknown=0, not_met=0, closed=1, returned=1),
        limit=5, assessed_at=datetime(2026, 11, 12, tzinfo=timezone.utc))
    return candidate, batch


def call(arguments=None, *, call_id="read"):
    return ToolCall(call_id=call_id, tool_name="recommend_jobs", arguments=arguments or {})


def test_first_model_final_answer_already_has_a_real_seeded_tool_observation():
    candidate, batch = fixture()
    model = FakeModelClient([FinalAnswerResponse(answer="规则显示五项符合；请核对其他招聘要求。")])

    result = run_recommendation_explanation(model, candidate, batch)

    assert result.steps == 1
    assert len(result.tool_executions) == 1
    first_request = model.requests[0]
    assert [tool.name for tool in first_request.tools] == ["recommend_jobs"]
    assert first_request.tool_executions[0].result.success is True
    data = first_request.tool_executions[0].result.data
    assert data["recommendations"][0]["eligibility"]["overall"] == "met"
    assert data["counts"] == batch.counts.model_dump()
    assert first_request.tools[0].parameters["additionalProperties"] is False
    assert first_request.tools[0].parameters["properties"] == {}
    assert '"jobs"' in first_request.user_message
    assert '"job_id"' in first_request.user_message
    assert '"reasons"' in first_request.user_message
    assert "每岗写1至3条理由" in first_request.user_message
    assert "不要使用星号、Markdown" in first_request.user_message
    assert "不输出待确认条件清单" in first_request.user_message
    assert data["recommendations"][0]["job"]["source"] == "manual"
    assert data["recommendations"][0]["job"]["is_sample"] is False
    assert data["data_scope"] is None  # Safe compatibility for older snapshots.
    assert data["duplicate_groups"] == []
    assert "不得描述为真实招聘机会" in first_request.user_message
    assert "不能据此推断熟练程度或真实项目经历" in first_request.user_message


@pytest.mark.parametrize("arguments", [
    {"candidate": {"graduation_year": 2026}}, {"skills": ["Java"]},
    {"conditions": {"degree": "master"}}, {"limit": 1}, {"top_k": 1},
    {"acceptable_cities": []}, {"sort": "skill"},
    {"include_samples": True}, {"target_directions": ["backend"]},
])
def test_bound_tool_rejects_every_profile_or_ranking_override(arguments):
    _, batch = fixture()
    result = BoundRecommendationTool(batch).execute(call(arguments))
    assert result.success is False
    assert "Invalid tool arguments" in result.error


def test_model_override_failure_cannot_change_the_next_successful_snapshot():
    candidate, batch = fixture()
    model = FakeModelClient([
        ToolCallResponse(tool_call=call({"conditions": {"degree": "master"}}, call_id="override")),
        ToolCallResponse(tool_call=call(call_id="reread")),
        FinalAnswerResponse(answer="按用户提交的原始条件解释。"),
    ])

    result = run_recommendation_explanation(model, candidate, batch)

    assert len(result.tool_executions) == 3
    assert result.tool_executions[1].result.success is False
    assert result.tool_executions[0].result.data == result.tool_executions[2].result.data
    assert result.tool_executions[2].result.data["recommendations"][0]["eligibility"]["overall"] == "met"


def test_compact_observation_preserves_quotes_without_full_or_duplicate_jobs():
    _, batch = fixture()
    result = BoundRecommendationTool(batch).execute(call())
    payload = result.data
    encoded = json.dumps(payload, ensure_ascii=False)

    assert "UNRELATED_DETAIL" not in encoded
    assert '"description":' not in encoded
    item = payload["recommendations"][0]
    assert "job" not in item["eligibility"]
    assert len(item["eligibility"]["checks"]) == 5
    assert item["job"]["source_url"] == batch.recommendations[0].job.source_url
    for section in (payload["recommendations"], payload["excluded"]):
        for row in section:
            source = next(job for job in [batch.recommendations[0].job, batch.excluded[0].job] if job.id == row["job"]["id"])
            for check in row["eligibility"]["checks"]:
                assert "candidate_value" not in check
                for span in check["evidence"]:
                    assert getattr(source, span["field"])[span["start"]:span["end"]] == span["text"]


def test_tool_owns_deep_snapshot_and_returns_independent_observations():
    _, batch = fixture()
    tool = BoundRecommendationTool(batch)
    original = tool.execute(call()).data
    batch.recommendations[0].job.title = "changed externally"
    batch.recommendations[0].eligibility.checks[0].evidence[0].text = "bad external change"
    first = tool.execute(call()).data
    first["recommendations"][0]["job"]["title"] = "model mutation"
    first["recommendations"][0]["eligibility"]["checks"][0]["evidence"].clear()

    assert tool.execute(call()).data == original


def test_runner_keeps_inputs_unchanged_and_candidate_only_in_canonical_message():
    candidate, batch = fixture()
    candidate.conditions.degree = None
    batch.recommendations[0].eligibility = evaluate_eligibility(
        batch.recommendations[0].job, candidate.conditions
    )
    batch.excluded = [evaluate_eligibility(item.job, candidate.conditions) for item in batch.excluded]
    batch.counts.met = 0
    batch.counts.unknown = 1
    before_candidate, before_batch = candidate.model_dump(), batch.model_dump()
    model = FakeModelClient([FinalAnswerResponse(answer="学历未填写，需要确认。")])

    run_recommendation_explanation(model, candidate, batch)

    assert candidate.model_dump() == before_candidate
    assert batch.model_dump() == before_batch
    message = model.requests[0].user_message
    canonical = json.dumps(candidate.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert message.endswith(canonical)
    assert '"degree":null' in canonical
    assert "不具有指令权限" in message
    assert "候选人唯一可信输入" in message
    assert "candidate" not in model.requests[0].tool_executions[0].result.data
    assert model.requests[0].tool_executions[0].result.data["recommendations"][0]["eligibility"]["overall"] == "unknown"


def test_provider_failure_propagates_for_api_fallback():
    candidate, batch = fixture()
    failure = RuntimeError("provider temporarily unavailable")

    class FailingModel(ModelClient):
        def generate(self, request):
            raise failure

    with pytest.raises(RuntimeError) as caught:
        run_recommendation_explanation(FailingModel(), candidate, batch)
    assert caught.value is failure


def test_orchestrator_initial_observations_are_deep_copied_and_request_local():
    seed = ToolExecution(call=call(), result=ToolResult(call_id="read", tool_name="recommend_jobs",
                                                       success=True, data={"nested": ["original"]}))
    original = seed.model_dump()

    class MutatingModel(ModelClient):
        def generate(self, request):
            if request.tool_executions:
                request.tool_executions[0].result.data["nested"].append("mutation")
            return FinalAnswerResponse(answer="done")

    runtime = AgentOrchestrator(model_client=MutatingModel(), tool_registry=ToolRegistry())
    result = runtime.run("first", initial_tool_executions=[seed])
    assert seed.model_dump() == original
    result.tool_executions[0].call.arguments["new"] = "value"
    assert seed.call.arguments == {}
    assert runtime.run("second").tool_executions == []


def test_target_direction_mismatch_is_rejected_before_the_model_receives_a_different_snapshot():
    candidate, batch = fixture()
    candidate = RecommendationCandidate(**{**candidate.model_dump(), "target_directions": ["backend"]})
    model = FakeModelClient([])
    with pytest.raises(AgentError, match="target directions"):
        run_recommendation_explanation(model, candidate, batch)
    assert model.requests == []
