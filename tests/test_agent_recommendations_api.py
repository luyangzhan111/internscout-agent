"""HTTP acceptance for authoritative recommendations and optional Agent prose."""

from pathlib import Path
import json
from datetime import datetime

from fastapi.testclient import TestClient
import pytest

from app.agent.contracts import FinalAnswerResponse, ToolCall, ToolCallResponse
from app.agent.model_client import ModelClient
from app.api.routes.recommendations import get_recommendation_model_factory
from app.api.routes import recommendations as recommendation_route
from app.database import JobModel, create_database_engine, create_session_factory, get_session
from app.database.repository import get_dataset_revision, upsert_job
from app.main import app
from app.schemas.job import JobCreate
from tests.agent.fakes.fake_model_client import FakeModelClient


@pytest.fixture
def api(tmp_path: Path, monkeypatch):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'agent-recommend.db').as_posix()}")
    factory = create_session_factory(engine)
    previous_engine = getattr(app.state, "database_engine", None)
    previous_overrides = dict(app.dependency_overrides)
    app.state.database_engine = engine

    def sessions():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    app.dependency_overrides[get_recommendation_model_factory] = lambda: lambda: None
    for key in ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "INTERNSCOUT_EMBEDDING_API_KEY", "INTERNSCOUT_EMBEDDING_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        if previous_engine is None:
            del app.state.database_engine
        else:
            app.state.database_engine = previous_engine
        engine.dispose()


def job_payload(**overrides):
    values = dict(
        title="软件实习生", company="测试公司", city="深圳", status="active",
        source_url="https://jobs.fixture.test/agent-eligibility/1", skills=["Python", "SQL"],
        description="面向2027届毕业生；本科及以上学历；工作经验不限；至少实习6个月。",
    )
    values.update(overrides)
    return values


def import_job(client, **overrides):
    response = client.post("/api/imports/manual", json={"jobs": [job_payload(**overrides)]})
    assert response.status_code == 200, response.text
    return response.json()["job_ids"][0]


def payload(**overrides):
    values = dict(candidate={
        "skills": ["Python"],
        "conditions": {"graduation_year": 2027, "degree": "bachelor", "degree_status": "completed",
                       "work_experience_months": 0, "acceptable_cities": ["深圳"], "internship_months": 6},
    }, limit=10, explain_with_model=True)
    values.update(overrides)
    return values


def recommend(client, **overrides):
    response = client.post("/api/agent/recommend", json=payload(**overrides))
    assert response.status_code == 200, response.text
    return response.json()


def bind_model(model):
    app.dependency_overrides[get_recommendation_model_factory] = lambda: lambda: model


def test_stage23_degree_branches_and_hybrid_evidence_reach_agent_cards(api):
    client, _ = api
    job_id = import_job(client, city="上海", description=(
        "招募本科生、硕士研究生。\n本科生需有项目经历，硕士研究生有研究经验优先。\n"
        "线上线下结合。\n使用Python开发应用。"))
    result = recommend(client, candidate={"skills": ["Python"], "conditions": {
        "degree": "master", "degree_status": "enrolled", "acceptable_cities": ["北京"]}},
        explain_with_model=False)
    assert result["counts"]["not_met"] == 0
    card = next(c for c in result["recommendations"] if c["job"]["id"] == job_id)
    checks = {c["dimension"]: c for c in card["eligibility"]["checks"]}
    assert checks["degree"]["status"] == "met" and checks["degree"]["notes"]
    assert checks["city"]["status"] == "unknown"
    assert checks["city"]["unknown_reason"] == "interpretation_uncertain"
    assert checks["city"]["next_step"]
    assert card["eligibility"]["rules_version"] == "stage23-rules-v1"
    assert any("线上线下结合" in q["text"] for q in checks["city"]["evidence"])
    for check in checks.values():
        for quote in check["evidence"]:
            assert card["job"][quote["field"]][quote["start"]:quote["end"]] == quote["text"]


def test_model_unavailable_keeps_rule_cards_and_does_not_write(api):
    client, factory = api
    job_id = import_job(client)
    before = client.get("/api/jobs").json()
    imports = client.get("/api/imports").json()
    with factory() as session:
        revision = get_dataset_revision(session)
    result = recommend(client)
    assert result["explanation_status"] == "unavailable"
    assert result["model_explanation"] is None
    assert result["job_explanations"] == []
    assert result["counts"] == dict(evaluated=1, met=1, unknown=0, not_met=0, closed=0, direction_mismatch=0, returned=1)
    card = result["recommendations"][0]
    assert card["job"]["id"] == job_id
    assert card["match_score"] == 50
    assert card["matched_skills"] == ["Python"]
    assert card["missing_skills"] == ["SQL"]
    assert card["eligibility"]["overall"] == "met"
    assert card["job"] == card["eligibility"]["job"]
    for check in card["eligibility"]["checks"]:
        for quote in check["evidence"]:
            assert card["job"][quote["field"]][quote["start"]:quote["end"]] == quote["text"]
    assert result["assessed_at"].endswith(("Z", "+00:00"))
    assert client.get("/api/jobs").json() == before
    assert client.get("/api/imports").json() == imports
    with factory() as session:
        assert get_dataset_revision(session) == revision


def test_missing_configuration_does_not_construct_sdk(api, monkeypatch):
    client, _ = api
    import_job(client)
    app.dependency_overrides.pop(get_recommendation_model_factory)
    monkeypatch.setattr(recommendation_route, "_bounded_model", lambda *args: pytest.fail("Missing config must not construct provider"))
    assert recommend(client)["explanation_status"] == "unavailable"


def test_dedicated_provider_has_short_timeout_and_no_retries(monkeypatch):
    calls = []
    sentinel = object()
    monkeypatch.setattr(recommendation_route, "OpenAI", lambda **kwargs: calls.append(kwargs) or sentinel)
    recommendation_route._bounded_model.cache_clear()
    try:
        model = recommendation_route._bounded_model("configured-test-model", "test-key-not-real")
        assert model.model == "configured-test-model"
        assert calls == [{"api_key": "test-key-not-real", "base_url": "https://api.deepseek.com", "timeout": 8.0, "max_retries": 0}]
    finally:
        recommendation_route._bounded_model.cache_clear()


def test_explanation_disabled_does_not_even_construct_provider(api):
    client, _ = api
    import_job(client)

    def forbidden():
        pytest.fail("Disabled explanations must not construct or call a provider")

    app.dependency_overrides[get_recommendation_model_factory] = lambda: forbidden
    result = recommend(client, explain_with_model=False)
    assert result["explanation_status"] == "disabled"
    assert result["steps"] == result["tool_execution_count"] == 0
    assert result["recommendations"]


def test_first_model_final_answer_cannot_skip_rule_results(api):
    client, _ = api
    import_job(client)
    model = FakeModelClient([FinalAnswerResponse(answer="这些只是补充建议。")])
    bind_model(model)
    result = recommend(client)
    assert result["explanation_status"] == "generated"
    assert result["model_explanation"] == "这些只是补充建议。"
    assert result["job_explanations"] == []
    assert "未能按岗位整理" in result["explanation_notice"]
    assert result["counts"]["met"] == 1
    assert result["tool_execution_count"] >= 1
    assert model.requests[0].tool_executions[0].result.success
    assert model.requests[0].tool_executions[0].result.tool_name == "recommend_jobs"


def test_model_cannot_fill_missing_degree_or_override_skills(api):
    client, _ = api
    import_job(client)
    model = FakeModelClient([
        ToolCallResponse(tool_call=ToolCall(call_id="override", tool_name="recommend_jobs", arguments={
            "candidate": {"skills": ["Python", "SQL"], "conditions": {"degree": "doctor"}},
        })),
        FinalAnswerResponse(answer="模型文本不是资格依据。"),
    ])
    bind_model(model)
    inputs = payload()["candidate"]
    inputs["conditions"].pop("degree")
    result = recommend(client, candidate=inputs)
    assert not model.requests[-1].tool_executions[-1].result.success
    card = result["recommendations"][0]
    assert card["match_score"] == 50
    assert card["eligibility"]["overall"] == "unknown"
    degree = next(check for check in card["eligibility"]["checks"] if check["dimension"] == "degree")
    assert degree["status"] == "unknown"


def test_provider_failure_preserves_complete_rules(api):
    client, _ = api
    import_job(client)

    class BrokenModel(ModelClient):
        def generate(self, request):
            raise TimeoutError("provider secret must not leak")

    bind_model(BrokenModel())
    result = recommend(client)
    assert result["explanation_status"] == "failed"
    assert result["model_explanation"] is None
    assert result["job_explanations"] == []
    assert result["counts"]["met"] == 1
    assert "secret" not in str(result)
    assert result["steps"] is None


def test_repeated_tool_calls_stop_at_three_model_steps_and_fall_back(api):
    client, _ = api
    import_job(client)
    model = FakeModelClient([
        ToolCallResponse(tool_call=ToolCall(call_id=f"repeat-{index}", tool_name="recommend_jobs", arguments={}))
        for index in range(5)
    ])
    bind_model(model)
    result = recommend(client)
    assert len(model.requests) == 3
    assert result["explanation_status"] == "failed"
    assert result["counts"]["met"] == 1
    assert result["steps"] is None


def test_current_update_rechecks_and_closed_jobs_are_counted_separately(api):
    client, _ = api
    first = import_job(client)
    before = recommend(client, explain_with_model=False)
    assert import_job(client, description="仅限2026届；硕士及以上学历；工作经验不限；实习时长不限。") == first
    changed = recommend(client, explain_with_model=False)
    assert changed["recommendations"] == []
    assert changed["counts"]["not_met"] == 1
    assert changed["excluded"][0]["source_fingerprint"] != before["recommendations"][0]["eligibility"]["source_fingerprint"]
    import_job(client, status="closed")
    closed = recommend(client, explain_with_model=False)
    assert closed["counts"] == dict(evaluated=1, met=0, unknown=0, not_met=0, closed=1, direction_mismatch=0, returned=0)
    assert closed["excluded"][0]["blocking_reasons"]


def test_changes_during_model_run_recompute_and_discard_old_prose(api):
    client, factory = api
    job_id = import_job(client)

    class ClosingModel(ModelClient):
        def generate(self, request):
            with factory() as session:
                upsert_job(session, JobCreate(**job_payload(status="closed"), source="manual"))
                session.commit()
            return FinalAnswerResponse(answer=json.dumps({"jobs": [
                {"job_id": job_id, "reasons": ["已失效的旧岗位说明"]},
            ]}, ensure_ascii=False))

    bind_model(ClosingModel())
    result = recommend(client)
    assert result["explanation_status"] == "stale"
    assert result["model_explanation"] is None
    assert result["job_explanations"] == []
    assert result["recommendations"] == []
    assert result["counts"]["closed"] == 1
    assert "已失效的旧岗位说明" not in str(result)


def test_structured_model_reasons_follow_current_rule_order_without_an_extra_call(api):
    client, _ = api
    first = import_job(client)
    second = import_job(client, source_url="https://jobs.fixture.test/agent-eligibility/2")
    raw = json.dumps({"jobs": [
        {"job_id": second, "reasons": ["岗位开发工作与你的 Python 技能相关。"]},
        {"job_id": first, "reasons": ["你的 Python 技能与岗位要求相符。", "可以进一步了解岗位中的接口开发工作。"]},
    ]}, ensure_ascii=False)
    model = FakeModelClient([FinalAnswerResponse(answer=raw)])
    bind_model(model)

    result = recommend(client)

    assert result["explanation_status"] == "generated"
    assert result["model_explanation"] == raw
    assert [item["job_id"] for item in result["job_explanations"]] == [first, second]
    assert result["job_explanations"][0]["reasons"] == ["你的 Python 技能与岗位要求相符。", "可以进一步了解岗位中的接口开发工作。"]
    assert len(model.requests) == 1
    assert [item["job"]["id"] for item in result["recommendations"]] == [first, second]


@pytest.mark.parametrize("kind", ["missing", "extra", "duplicate", "markdown", "technical_code"])
def test_invalid_structured_reasons_keep_raw_text_and_rule_cards_without_retry(api, kind):
    client, _ = api
    job_id = import_job(client)
    jobs = [{"job_id": job_id, "reasons": ["Python 技能与你的开发方向相关。"]}]
    if kind == "missing":
        jobs = []
    elif kind == "extra":
        jobs.append({"job_id": 999999, "reasons": ["不存在岗位的理由。"]})
    elif kind == "duplicate":
        jobs += jobs
    elif kind == "markdown":
        jobs[0]["reasons"] = ["**推荐理由**"]
    else:
        jobs[0]["reasons"] = ["match_score 为100。"]
    raw = json.dumps({"jobs": jobs}, ensure_ascii=False)
    model = FakeModelClient([FinalAnswerResponse(answer=raw)])
    bind_model(model)

    result = recommend(client)

    assert result["explanation_status"] == "generated"
    assert result["model_explanation"] == raw
    assert result["job_explanations"] == []
    assert result["recommendations"][0]["job"]["id"] == job_id
    assert "未能按岗位整理" in result["explanation_notice"]
    assert len(model.requests) == 1


def test_empty_and_all_rejected_are_distinct_and_do_not_call_model(api):
    client, _ = api

    def forbidden():
        pytest.fail("No recommendations should skip optional provider")

    app.dependency_overrides[get_recommendation_model_factory] = lambda: forbidden
    empty = recommend(client)
    assert empty["counts"]["evaluated"] == 0
    assert empty["explanation_status"] == "not_needed"
    import_job(client, description="仅限2026届毕业生")
    rejected = recommend(client)
    assert rejected["counts"]["not_met"] == 1
    assert rejected["excluded"][0]["overall"] == "not_met"
    assert rejected["summary"] != empty["summary"]


def test_ranking_before_cutoff_and_multicity_survive(api):
    client, _ = api
    for index in range(5):
        import_job(client, source_url=f"https://jobs.fixture.test/high-rejected/{index}",
                   skills=["Python"], description="仅限2026届毕业生")
    low_met = import_job(client, source_url="https://jobs.fixture.test/low-met", city="北京、深圳")
    unknown = import_job(client, source_url="https://jobs.fixture.test/high-unknown", skills=["Python"], description="负责软件开发。")
    result = recommend(client, explain_with_model=False, limit=2)
    assert [item["job"]["id"] for item in result["recommendations"]] == [low_met, unknown]
    assert [item["eligibility"]["overall"] for item in result["recommendations"]] == ["met", "unknown"]
    assert result["counts"]["not_met"] == 5


def test_continuously_changing_source_returns_retry_not_stale_cards(api, monkeypatch):
    client, _ = api
    import_job(client)
    revisions = iter(range(10))
    monkeypatch.setattr("app.api.routes.recommendations.get_dataset_revision", lambda session: next(revisions))
    result = client.post("/api/agent/recommend", json=payload(explain_with_model=False))
    assert result.status_code == 409
    assert "recommendations" not in result.json()


@pytest.mark.parametrize("changes", [
    {"limit": 0}, {"limit": 51}, {"limit": True}, {"limit": "10"},
    {"explain_with_model": "false"}, {"resume": "unexpected"},
    {"include_samples": "false"}, {"include_samples": 1}, {"include_samples": None},
    {"candidate": {"skills": []}}, {"candidate": {"skills": [" "]}},
    {"candidate": {"skills": [4]}}, {"candidate": {"skills": ["x" * 101]}},
    {"candidate": {"skills": ["x"] * 101}},
    {"candidate": {"skills": ["Python"], "conditions": {"degree": "phd"}}},
    {"candidate": {"skills": ["Python"], "conditions": {"work_experience_months": -1}}},
    {"candidate": {"skills": ["Python"], "conditions": {"graduation_year": True}}},
    {"candidate": {"skills": ["Python"], "conditions": {"acceptable_cities": [1]}}},
    {"candidate": {"skills": ["Python"], "conditions": {"invented": "condition"}}},
])
def test_invalid_inputs_are_rejected(api, changes):
    client, _ = api
    assert client.post("/api/agent/recommend", json=payload(**changes)).status_code == 422


def test_default_sample_isolation_skips_model_then_explicit_demo_labels_model_observation(api):
    client, _ = api
    job_id = import_job(client, source_url="https://jobs.EXAMPLE.com./sample/1")
    def forbidden():
        pytest.fail("Isolated samples must never reach the model factory")
    app.dependency_overrides[get_recommendation_model_factory] = lambda: forbidden
    isolated = recommend(client)
    assert isolated["explanation_status"] == "not_needed"
    assert isolated["recommendations"] == []
    assert isolated["data_scope"] == dict(total_records=1, sample_records_excluded=1,
        duplicate_records_collapsed=0, include_samples=False)
    assert "隔离 1 条样例" in isolated["summary"]
    assert "岗位库目前为空" not in isolated["summary"]
    model = FakeModelClient([FinalAnswerResponse(answer=json.dumps({"jobs": [
        {"job_id": job_id, "reasons": ["Python 技能与样例开发工作有交集。"]}
    ]}, ensure_ascii=False))])
    bind_model(model)
    included = recommend(client, include_samples=True)
    assert included["counts"]["evaluated"] == 1 and included["data_scope"]["include_samples"]
    observation = model.requests[0].tool_executions[0].result.data
    assert observation["recommendations"][0]["job"]["is_sample"] is True
    assert observation["recommendations"][0]["job"]["source"] == "manual"
    assert observation["data_scope"]["sample_records_excluded"] == 0
    assert "不得描述为真实招聘机会" in model.requests[0].user_message


def test_api_groups_cross_source_records_without_deleting_them_or_reviving_closed_official_job(api):
    client, factory = api
    url = "https://career.oppo.com/official/oppo/recruitment/post/123?recruitType=intern"
    manual_id = import_job(client, source_url=url, company="OPPO")
    with factory() as session:
        official_id = upsert_job(session, JobCreate(**job_payload(source_url=url, company="OPPO", status="closed"),
                                                  source="oppo", source_job_id="123")).job.id
    before = client.get("/api/jobs").json()
    result = recommend(client, explain_with_model=False)
    assert result["data_scope"] == dict(total_records=2, sample_records_excluded=0,
        duplicate_records_collapsed=1, include_samples=False)
    assert result["recommendations"] == [] and result["counts"]["closed"] == 1
    assert result["duplicate_groups"][0]["primary_job_id"] == official_id
    assert [item["job_id"] for item in result["duplicate_groups"][0]["sources"]] == [manual_id, official_id]
    assert result["duplicate_groups"][0]["has_conflict"] is True
    assert client.get("/api/jobs").json() == before


def test_new_official_duplicate_during_model_call_replaces_primary_and_discards_old_reason(api):
    client, factory = api
    url = "https://career.oppo.com/official/oppo/recruitment/post/456"
    manual_id = import_job(client, source_url=url, company="OPPO")
    inserted = []
    class AddingOfficialModel(ModelClient):
        def generate(self, request):
            with factory() as session:
                inserted.append(upsert_job(session, JobCreate(**job_payload(source_url=url, company="OPPO"),
                    source="oppo", source_job_id="456")).job.id)
            return FinalAnswerResponse(answer=json.dumps({"jobs": [
                {"job_id": manual_id, "reasons": ["这段旧来源说明必须丢弃。"]}
            ]}, ensure_ascii=False))
    bind_model(AddingOfficialModel())
    result = recommend(client)
    assert result["explanation_status"] == "stale" and result["model_explanation"] is None
    assert result["job_explanations"] == []
    assert result["recommendations"][0]["job"]["id"] == inserted[0]
    assert result["data_scope"]["duplicate_records_collapsed"] == 1


def test_observation_only_update_switches_primary_without_revision_and_discards_stale_ai(api):
    client, factory = api
    url = "https://careers.acme.test/observation-only"
    manual_id = import_job(client, source_url=url)
    with factory() as session:
        other_id = upsert_job(session, JobCreate(**job_payload(source_url=url, status="closed"), source="other_feed")).job.id
        for job_id, checked in ((manual_id, datetime(2026, 1, 2)), (other_id, datetime(2026, 1, 1))):
            job = session.get(JobModel, job_id)
            job.updated_at = job.last_checked_at = checked
        session.commit()
        revision = get_dataset_revision(session)
    class ObservationModel(ModelClient):
        def generate(self, request):
            assert request.tool_executions[0].result.data["recommendations"][0]["job"]["id"] == manual_id
            with factory() as session:
                session.get(JobModel, other_id).last_checked_at = datetime(2026, 1, 3)
                session.commit()
                assert get_dataset_revision(session) == revision
            return FinalAnswerResponse(answer="已经过时的岗位说明。")
    bind_model(ObservationModel())
    result = recommend(client)
    assert result["explanation_status"] == "stale"
    assert result["model_explanation"] is None and result["job_explanations"] == []
    assert result["recommendations"] == [] and result["counts"]["closed"] == 1
    assert result["duplicate_groups"][0]["primary_job_id"] == other_id


def test_rules_only_refresh_does_not_claim_a_model_explanation_was_discarded(api, monkeypatch):
    client, _ = api
    import_job(client)
    original = recommendation_route._stable_batch
    calls = 0
    def changing_snapshot(*args, **kwargs):
        nonlocal calls
        batch, revision = original(*args, **kwargs)
        calls += 1
        if calls == 2:
            return batch, revision + 1
        return batch, revision
    monkeypatch.setattr(recommendation_route, "_stable_batch", changing_snapshot)
    result = recommend(client, explain_with_model=False)
    assert result["explanation_status"] == "disabled"
    assert "已重新判断" in result["explanation_notice"]
    assert "旧说明已舍弃" not in result["explanation_notice"]


def test_initial_empty_result_refreshed_to_available_jobs_has_truthful_no_model_notice(api, monkeypatch):
    client, factory = api
    original = recommendation_route._stable_batch
    calls = 0
    def newly_available(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            with factory() as session:
                upsert_job(session, JobCreate(**job_payload(), source="manual"))
        return original(*args, **kwargs)
    monkeypatch.setattr(recommendation_route, "_stable_batch", newly_available)
    result = recommend(client)
    assert result["recommendations"] and result["explanation_status"] == "not_needed"
    assert "本次未调用模型" in result["explanation_notice"]
    assert "没有可推荐岗位" not in result["explanation_notice"]
    assert "旧说明已舍弃" not in result["explanation_notice"]


def test_all_unrelated_jobs_leave_qualification_intact_and_skip_ai(api):
    client, _ = api
    job_id = import_job(client, title="公关经理", description=job_payload()["description"] + "了解Python工具优先。")
    profile = {**payload()["candidate"], "target_directions": ["backend"]}
    def forbidden():
        pytest.fail("No recommendation should call a provider.")
    app.dependency_overrides[get_recommendation_model_factory] = lambda: forbidden
    result = recommend(client, candidate=profile)
    assert result["explanation_status"] == "not_needed"
    assert result["target_directions"] == ["backend"]
    assert result["counts"]["direction_mismatch"] == 1 and result["counts"]["not_met"] == 0
    assert result["recommendations"] == result["excluded"] == []
    excluded = result["direction_excluded"][0]
    assert excluded["job"]["id"] == job_id and excluded["eligibility"]["overall"] == "met"
    assert excluded["direction_fit"]["status"] == "unrelated"
    assert "所有岗位的明确方向都与本次选择不同" in result["summary"]


def test_targeted_model_observation_contains_only_current_quality_evidence_and_ids(api):
    client, _ = api
    included = import_job(client, title="后端开发工程师", description=job_payload()["description"] + "必须掌握Python；SQL优先。")
    unrelated = import_job(client, title="公关经理", source_url="https://jobs.fixture.test/pr")
    profile = {**payload()["candidate"], "target_directions": ["backend", "backend"]}
    model = FakeModelClient([FinalAnswerResponse(answer=json.dumps({"jobs": [
        {"job_id": included, "reasons": ["岗位原文的开发要求与你填写的 Python 有交集。"]},
    ]}, ensure_ascii=False))])
    bind_model(model)
    result = recommend(client, candidate=profile)
    observation = model.requests[0].tool_executions[0].result.data
    assert result["explanation_status"] == "generated" and result["job_explanations"][0]["job_id"] == included
    assert observation["target_directions"] == ["backend"] and observation["ranking_version"] == "direction-support-v4"
    assert [row["job"]["id"] for row in observation["recommendations"]] == [included]
    assert [row["job"]["id"] for row in observation["direction_excluded"]] == [unrelated]
    card = result["recommendations"][0]
    seen = observation["recommendations"][0]
    assert seen["direction_fit"] == card["direction_fit"]
    assert seen["skill_requirements"] == card["skill_requirements"]
    assert [(r["skill"], r["importance"], r["matched"]) for r in seen["skill_requirements"]] == [
        ("Python", "core", True), ("SQL", "bonus", False),
    ]
    for group in [seen["direction_fit"], *seen["skill_requirements"]]:
        for span in group["evidence"]:
            assert card["job"][span["field"]][span["start"]:span["end"]] == span["text"]
    assert "缺乏技能证据不能推断门槛低或适合候选人" in model.requests[0].user_message


def test_role_change_during_model_call_moves_job_to_direction_exclusions_and_discards_old_prose(api):
    client, factory = api
    job_id = import_job(client, title="后端开发工程师")
    profile = {**payload()["candidate"], "target_directions": ["backend"]}
    class UpdatedRole(ModelClient):
        def generate(self, request):
            with factory() as session:
                assert upsert_job(session, JobCreate(**job_payload(title="公关经理"), source="manual")).job.id == job_id
            return FinalAnswerResponse(answer="这份旧开发岗位说明。")
    bind_model(UpdatedRole())
    result = recommend(client, candidate=profile)
    assert result["explanation_status"] == "stale" and result["job_explanations"] == []
    assert result["model_explanation"] is None and result["recommendations"] == []
    assert result["counts"]["direction_mismatch"] == 1 and result["counts"]["not_met"] == 0
    assert result["direction_excluded"][0]["job"]["id"] == job_id
