"""Structured recommendation UI with controlled HTTP and no model calls."""

import copy
import json
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from demo.data_client import JobDataApiClient
from demo.recommendation_client import RecommendationApiClient


APP_PATH = Path(__file__).resolve().parents[2] / "demo" / "app.py"


def _eligibility(job_id=1, overall="unknown", *, closed=False):
    job = {
        "id": job_id, "title": f"岗位{job_id}", "company": "示例公司", "city": "深圳",
        "description": "本科及以上；<b>岗位原文</b>", "source": "manual",
        "source_url": f"https://example.com/jobs/{job_id}", "status": "closed" if closed else "unknown",
    }
    return {
        "job": job, "overall": overall, "reason": "测试规则结果",
        "checks": [{
            "dimension": dimension, "status": overall, "reason": "测试条件理由",
            "candidate_value": "未填写", "requirement": "本科及以上",
            "evidence": [{"field": "description", "text": "本科及以上", "start": 0, "end": 5}],
            "notes": ["硕士优先，只作为偏好"],
        } for dimension in ("graduation_year", "degree", "experience", "city", "internship_duration")],
        "blocking_reasons": ["明确条件不满足"] if overall == "not_met" else [],
        "source_fingerprint": "test", "rules_version": "test-v1",
    }


def _recommendation(job_id=1, overall="unknown", score=50):
    result = _eligibility(job_id, overall)
    return {
        "job": copy.deepcopy(result["job"]), "match_score": score,
        "matched_skills": ["Python"], "missing_skills": ["SQL"],
        "detected_job_skills": ["Python", "SQL"], "reason": "partial_match", "eligibility": result,
    }


def _payload():
    return {
        "recommendations": [_recommendation()], "excluded": [],
        "counts": {"evaluated": 1, "met": 0, "unknown": 1, "not_met": 0, "closed": 0, "returned": 1},
        "limit": 10, "assessed_at": "2026-11-12T01:00:00", "summary": "推荐 1 个待确认岗位。",
        "model_explanation": None, "explanation_status": "disabled",
        "explanation_notice": "未启用 AI 补充说明，以上为规则结果。",
    }


def _start(monkeypatch, payload=None, *, full_app=False):
    state = {"payload": payload or _payload(), "fail": False, "bad_json": False}
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/api/jobs":
            return httpx.Response(200, json={"items": [], "total": 0, "page": 1, "page_size": 20, "pages": 0})
        assert request.url.path == "/api/agent/recommend"
        if state["fail"]:
            return httpx.Response(500, json={"detail": "offline"})
        if state["bad_json"]:
            return httpx.Response(200, text="invalid JSON")
        return httpx.Response(200, json=state["payload"])

    transport = httpx.MockTransport(handler)
    client = RecommendationApiClient(transport=transport)
    data_client = JobDataApiClient(transport=transport)
    monkeypatch.setattr(RecommendationApiClient, "from_env", lambda: client)
    monkeypatch.setattr(JobDataApiClient, "from_env", lambda: data_client)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    if full_app:
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        app.radio[0].set_value("Agent 推荐").run()
    else:
        app = AppTest.from_string(
            "from demo.recommendation_page import render_agent_recommendations\nrender_agent_recommendations()",
            default_timeout=10,
        ).run()
    assert not app.exception
    return app, state, requests


def _field(widgets, label):
    return next(widget for widget in widgets if widget.label == label)


def _recommend(app):
    _field(app.button, "获取推荐").click().run()
    assert not app.exception


def _fill_skills(app):
    _field(app.text_input, "你的技能（至少一项，逗号分隔）").set_value("Python").run()


def test_page_uses_structured_endpoint_and_unknown_city_by_default(monkeypatch):
    app, _, requests = _start(monkeypatch, full_app=True)
    assert not any(request.method == "POST" for request in requests)
    _fill_skills(app)
    _recommend(app)
    request = [request for request in requests if request.method == "POST"][0]
    payload = json.loads(request.content)
    assert payload["candidate"]["skills"] == ["Python"]
    assert all(value is None for value in payload["candidate"]["conditions"].values())
    assert payload["explain_with_model"] is False
    assert payload["include_samples"] is False
    assert [item.value for item in app.metric][:4] == ["0", "1", "0", "0"]
    assert any("50/100" == item.value for item in app.metric)
    assert any("<b>岗位原文</b>" in item.value for item in app.text)
    assert not any("<b>岗位原文</b>" in item.value for item in app.markdown)
    assert any("未启用 AI 补充说明" in item.value for item in app.info)


@pytest.mark.parametrize("status", ["unavailable", "failed", "stale", "disabled"])
def test_model_fallback_preserves_rule_cards(monkeypatch, status):
    payload = _payload()
    payload.update(explanation_status=status, explanation_notice=f"模型说明状态：{status}")
    app, _, requests = _start(monkeypatch, payload)
    if status != "disabled":
        _field(app.checkbox, "AI 补充说明").check().run()
    _fill_skills(app)
    _recommend(app)
    sent = next(request for request in requests if request.method == "POST")
    assert json.loads(sent.content)["explain_with_model"] == (status != "disabled")
    assert any(item.value == "50/100" for item in app.metric)
    assert any(f"模型说明状态：{status}" in item.value for item in app.info)
    assert not app.error


@pytest.mark.parametrize("kind", ["empty", "blocked"])
def test_empty_and_all_blocked_states_are_distinct(monkeypatch, kind):
    payload = _payload()
    payload.update(recommendations=[], explanation_status="not_needed")
    payload["counts"].update(evaluated=0, unknown=0, returned=0)
    if kind == "blocked":
        payload["counts"].update(evaluated=2, not_met=1, closed=1)
        payload["excluded"] = [_eligibility(2, "not_met"), _eligibility(3, "not_met", closed=True)]
    app, _, _ = _start(monkeypatch, payload)
    _fill_skills(app)
    _recommend(app)
    expected = "岗位库为空" if kind == "empty" else "本次没有可推荐岗位"
    assert any(expected in item.value for item in app.info)
    assert len(app.metric) == 4
    if kind == "blocked":
        assert any("未推荐岗位的阻断依据" in item.label for item in app.expander)
        assert any("明确条件不满足" in item.value for item in app.text)


def test_model_explanation_cannot_change_card_order(monkeypatch):
    payload = _payload()
    payload["recommendations"] = [_recommendation(1, "met", 10), _recommendation(2, "unknown", 100)]
    payload["counts"].update(evaluated=2, met=1, returned=2)
    payload.update(explanation_status="generated", model_explanation="先关注岗位2。")
    app, _, _ = _start(monkeypatch, payload)
    _fill_skills(app)
    _recommend(app)
    texts = [item.value for item in app.text]
    headings = [item.value for item in app.markdown if 'class="is-job-heading"' in item.value]
    assert len(headings) == 2
    assert "<h3>岗位1</h3>" in headings[0]
    assert "<h3>岗位2</h3>" in headings[1]
    # Unbound prose cannot be guessed onto a job or change the server order.
    assert "先关注岗位2。" not in texts
    assert any("无法对应到具体岗位" in item.value for item in app.info)


def test_ai_reasons_are_grouped_with_authoritative_conditions_and_exact_evidence(monkeypatch):
    payload = _payload()
    payload["recommendations"] = [_recommendation(1, "met", 10), _recommendation(2, "unknown", 100)]
    payload["counts"].update(evaluated=2, met=1, returned=2)
    payload.update(
        explanation_status="generated", model_explanation="internal raw JSON should not render",
        job_explanations=[
            {"job_id": 1, "reasons": ["**Python** 技能有交集。"]},
            {"job_id": 2, "reasons": ["可以重点核对 SQL 要求。"]},
        ],
    )
    app, _, requests = _start(monkeypatch, payload)
    _fill_skills(app)
    _recommend(app)
    texts = [item.value for item in app.text]
    assert texts.index("• Python 技能有交集。") < texts.index("• 可以重点核对 SQL 要求。")
    assert not any("internal raw JSON" in value or "**" in value for value in texts)
    assert sum(item.value == "#### 推荐理由" for item in app.markdown) == 2
    assert sum(item.value == "#### 待确认条件" for item in app.markdown) == 2
    assert sum(item.value == "#### 原文依据" for item in app.markdown) == 2
    assert any("五项无待确认项" in item.value for item in app.caption)
    assert "本科及以上" in texts
    assert "<b>岗位原文</b>" in "\n".join(texts)
    assert not any("<b>岗位原文</b>" in item.value for item in app.markdown)
    assert [item.value for item in app.metric][:4] == ["1", "1", "0", "0"]
    app.run()
    assert len([request for request in requests if request.method == "POST"]) == 1


def test_previous_generated_text_is_readable_without_repeating_model_request(monkeypatch):
    payload = _payload()
    payload.update(explanation_status="generated", model_explanation=(
        "**说明 assessed_at 2026-11-13**\n\n"
        "1. **ID 1 · 岗位1 · 示例公司 · 深圳**（active）\n"
        "   - 技能覆盖率 50：命中 **Python**；缺失 SQL。\n"
        "   - 资格：**待确认**（overall=unknown）。\n\n"
        "**提醒**：技能不等于录用概率。"
    ))
    app, _, requests = _start(monkeypatch, payload)
    _fill_skills(app)
    _recommend(app)
    shown = "\n".join(item.value for item in app.text)
    assert "技能覆盖率 50" in shown and "命中 Python" in shown
    assert all(token not in shown for token in ("**", "assessed_at", "overall=unknown", "（active）"))
    assert any("待确认条件" in item.value for item in app.markdown)
    app.run()
    assert len([request for request in requests if request.method == "POST"]) == 1


def test_bad_ai_format_without_legacy_text_keeps_rule_cards(monkeypatch):
    payload = _payload()
    payload.update(explanation_status="generated", model_explanation=None,
                   job_explanations=[{"job_id": 999, "reasons": ["不能关联的说明"]}])
    app, _, _ = _start(monkeypatch, payload)
    _fill_skills(app)
    _recommend(app)
    assert not app.error
    assert any(item.value == "50/100" for item in app.metric)
    assert any("格式不完整" in item.value for item in app.info)
    assert not any("不能关联的说明" in item.value for item in app.text)


@pytest.mark.parametrize("change", ["skills", "conditions", "limit", "ai", "samples", "refresh"])
def test_input_change_and_refresh_hide_old_results_without_model_request(monkeypatch, change):
    app, _, requests = _start(monkeypatch)
    _fill_skills(app)
    _recommend(app)
    assert app.metric
    if change == "skills":
        _field(app.text_input, "你的技能（至少一项，逗号分隔）").set_value("SQL").run()
    elif change == "conditions":
        _field(app.text_input, "毕业年份（可选）").set_value("2027").run()
    elif change == "limit":
        _field(app.number_input, "最多展示岗位数").set_value(5).run()
    elif change == "ai":
        _field(app.checkbox, "AI 补充说明").check().run()
    elif change == "samples":
        _field(app.checkbox, "包含演示数据（仅用于体验）").check().run()
    elif change == "refresh":
        _field(app.button, "刷新 / 清除旧结果").click().run()
    assert not app.exception
    assert not app.metric
    assert len([request for request in requests if request.method == "POST"]) == 1


@pytest.mark.parametrize("failure", ["fail", "bad_json", "bad_quote"])
def test_new_request_failure_never_leaves_previous_results(monkeypatch, failure):
    app, state, requests = _start(monkeypatch)
    _fill_skills(app)
    _recommend(app)
    if failure == "bad_quote":
        state["payload"]["recommendations"][0]["eligibility"]["checks"][0]["evidence"][0]["text"] = "硕士及以上"
    else:
        state[failure] = True
    _recommend(app)
    assert not app.metric
    assert app.error
    assert len([request for request in requests if request.method == "POST"]) == 2


def test_explicit_zero_unrestricted_city_and_draft_survive_navigation(monkeypatch):
    app, _, requests = _start(monkeypatch, full_app=True)
    _fill_skills(app)
    _field(app.text_input, "正式工作经验（月，可选）").set_value("0").run()
    _field(app.selectbox, "可接受的城市").set_value("unrestricted").run()
    _recommend(app)
    body = json.loads([request for request in requests if request.method == "POST"][-1].content)
    assert body["candidate"]["conditions"]["work_experience_months"] == 0
    assert body["candidate"]["conditions"]["acceptable_cities"] == []
    app.radio[0].set_value("岗位库").run()
    app.radio[0].set_value("Agent 推荐").run()
    assert not app.exception
    assert _field(app.text_input, "正式工作经验（月，可选）").value == "0"
    assert _field(app.selectbox, "可接受的城市").value == "unrestricted"
    assert len([request for request in requests if request.method == "POST"]) == 1


def _provenance_payload():
    payload = _payload()
    payload["excluded"] = [_eligibility(2, "not_met", closed=True)]
    payload["counts"].update(evaluated=2, closed=1)
    jobs = [payload["recommendations"][0]["job"], payload["excluded"][0]["job"]]
    groups = []
    for job in jobs:
        job.update(source="oppo", source_url=f"https://career.oppo.com/jobs/{job['id']}",
                   updated_at="2026-11-14T01:00:00", last_checked_at="2026-11-14T01:30:00")
        source = {key: job.get(key) for key in (
            "source", "source_url", "status", "last_checked_at", "updated_at", "title", "company"
        )}
        source["job_id"] = job["id"]
        groups.append({
            "primary_job_id": job["id"], "has_conflict": True,
            "selection_reason": "优先采用官网来源；原文不与副本拼接。",
            "sources": [source, dict(source, job_id=job["id"] + 10, source="manual", status="active")],
        })
    payload["recommendations"][0]["eligibility"]["job"] = copy.deepcopy(jobs[0])
    payload["duplicate_groups"] = groups
    payload["data_scope"] = {
        "total_records": 7, "sample_records_excluded": 3,
        "duplicate_records_collapsed": 2, "include_samples": False,
    }
    return payload


def test_scope_summary_and_both_recommended_and_excluded_sources_are_visible(monkeypatch):
    payload = _provenance_payload()
    app, _, _ = _start(monkeypatch, payload)
    _fill_skills(app)
    _recommend(app)
    captions = "\n".join(item.value for item in app.caption)
    texts = "\n".join(item.value for item in app.text)
    assert "读取 7 条原始记录 → 隔离 3 条演示记录 → 合并 2 条重复记录 → 判断 2 个独立岗位" in captions
    assert "匹配 1 / 已识别 2 项" in texts
    assert [item.value for item in app.metric][:4] == ["0", "1", "0", "1"]
    assert sum(item.label == "查看合并来源（2 条记录）" for item in app.expander) == 2
    assert "主来源 · OPPO 官网 · 记录 1" in texts
    assert "其他来源 · 手动导入 · 记录 12" in texts
    assert "主来源选择：优先采用官网来源" in texts
    assert "合并来源存在差异" in captions
    assert "本地处理时间：2026-11-14 09:30（北京时间）" in captions
    assert "最近核验：2026-11-14 09:30（北京时间）" in captions
    assert any("没有拼接" in item.value for item in app.warning)
    assert "本科及以上" in texts


def test_all_samples_isolated_is_not_reported_as_empty_library(monkeypatch):
    payload = _payload()
    payload.update(recommendations=[], explanation_status="not_needed", data_scope={
        "total_records": 3, "sample_records_excluded": 3,
        "duplicate_records_collapsed": 0, "include_samples": False,
    })
    payload["counts"].update(evaluated=0, unknown=0, returned=0)
    app, _, _ = _start(monkeypatch, payload)
    _fill_skills(app)
    _recommend(app)
    assert any("均为演示数据" in item.value for item in app.info)
    assert not any("岗位库为空" in item.value for item in app.info)


def test_explicit_sample_mode_is_submitted_and_manual_example_link_is_marked(monkeypatch):
    payload = _payload()
    payload["data_scope"] = {
        "total_records": 1, "sample_records_excluded": 0,
        "duplicate_records_collapsed": 0, "include_samples": True,
    }
    app, _, requests = _start(monkeypatch, payload, full_app=True)
    _fill_skills(app)
    _field(app.checkbox, "包含演示数据（仅用于体验）").check().run()
    _recommend(app)
    body = json.loads([request for request in requests if request.method == "POST"][-1].content)
    assert body["include_samples"] is True
    assert any("演示模式" in item.value for item in app.warning)
    assert any("样例岗位" in item.value for item in app.warning)
    app.radio[0].set_value("岗位库").run()
    app.radio[0].set_value("Agent 推荐").run()
    assert _field(app.checkbox, "包含演示数据（仅用于体验）").value is True
    assert len([request for request in requests if request.method == "POST"]) == 1


def test_four_unknown_categories_and_next_steps_remain_plain_text(monkeypatch):
    payload = _payload()
    pairs = [
        ("candidate_missing", "个人信息缺失"), ("source_unspecified", "原文未说明"),
        ("interpretation_uncertain", "无法可靠判断"), ("requirements_conflict", "要求冲突"),
    ]
    for check, (category, _) in zip(payload["recommendations"][0]["eligibility"]["checks"], pairs):
        check.update(unknown_reason=category, next_step="核对 <b>原文要求</b>")
    app, _, _ = _start(monkeypatch, payload)
    _fill_skills(app)
    _recommend(app)
    captions = "\n".join(item.value for item in app.caption)
    for _, label in pairs:
        assert f"待确认类型：{label}" in captions
    assert any("下一步：核对 <b>原文要求</b>" == item.value for item in app.text)
    assert not any("<b>原文要求</b>" in item.value for item in app.markdown)


def test_zero_identified_skills_explain_insufficient_evidence(monkeypatch):
    payload = _payload()
    payload["recommendations"][0].update(
        match_score=0, matched_skills=[], missing_skills=[], detected_job_skills=[],
        reason="insufficient_evidence",
    )
    app, _, _ = _start(monkeypatch, payload)
    _fill_skills(app)
    _recommend(app)
    assert any(item.value == "匹配 0 / 已识别 0 项" for item in app.text)
    assert any("岗位技能证据不足" in item.value for item in app.caption)


def test_old_cached_response_missing_new_fields_remains_readable_without_guessing(monkeypatch):
    app, _, requests = _start(monkeypatch)
    _fill_skills(app)
    _recommend(app)
    response = app.session_state["recommendation_current_result"]["response"]
    response.__dict__.pop("data_scope", None)
    response.__dict__.pop("duplicate_groups", None)
    response.__dict__.pop("ranking_version", None)
    response.__dict__.pop("target_directions", None)
    response.__dict__.pop("direction_excluded", None)
    response.counts.__dict__.pop("direction_mismatch", None)
    response.recommendations[0].__dict__.pop("direction_fit", None)
    response.recommendations[0].__dict__.pop("skill_requirements", None)
    app.session_state["recommendation_current_result"]["draft"].pop("target_directions", None)
    for check in response.recommendations[0].eligibility.checks:
        check.__dict__.pop("unknown_reason", None)
        check.__dict__.pop("next_step", None)
    app.run()
    assert not app.exception
    assert any("没有数据范围信息" in item.value for item in app.warning)
    assert not any("待确认类型" in item.value for item in app.caption)
    assert any(item.value == "50/100" for item in app.metric)
    assert len([request for request in requests if request.method == "POST"]) == 1


def _quality_payload():
    payload = _provenance_payload()
    item = payload["recommendations"][0]
    job = item["job"]
    description = job["description"] + "。要求掌握Python，有SQL经验者优先。"
    job.update(title="后端开发", description=description)
    item["eligibility"]["job"] = copy.deepcopy(job)
    for source in payload["duplicate_groups"][0]["sources"]:
        source["title"] = job["title"]
    def quote(text):
        start = description.index(text)
        return {"field": "description", "text": text, "start": start, "end": start + len(text)}
    item.update(direction_fit={
        "status": "aligned", "detected_directions": ["backend"], "reason": "名称说明岗位承担后端开发。",
        "evidence": [{"field": "title", "start": 0, "end": 4, "text": "后端开发"}],
    }, skill_requirements=[
        {"skill": "Python", "importance": "core", "matched": True, "evidence": [quote("要求掌握Python")]},
        {"skill": "SQL", "importance": "bonus", "matched": False, "evidence": [quote("有SQL经验者优先")]},
    ])
    # The second source group now belongs to a direction exclusion with actual met eligibility.
    unrelated = _recommendation(2, "met")
    unrelated["job"] = payload["excluded"][0]["job"]
    unrelated["job"].update(title="市场公关", status="active", description=description)
    unrelated["eligibility"]["job"] = copy.deepcopy(unrelated["job"])
    unrelated.update(direction_fit={
        "status": "unrelated", "detected_directions": ["other"], "reason": "岗位名称说明是市场公关方向。",
        "evidence": [{"field": "title", "start": 0, "end": 4, "text": "市场公关"}],
    }, skill_requirements=copy.deepcopy(item["skill_requirements"]))
    second_group = payload["duplicate_groups"][1]
    for source in second_group["sources"]:
        source["title"] = "市场公关"
    second_group["sources"][0]["status"] = "active"
    payload.update(ranking_version="direction-core-v1", target_directions=["backend", "security"],
                   direction_excluded=[unrelated], excluded=[])
    payload["counts"].update(closed=0, direction_mismatch=1)
    return payload


def _select_targets(app):
    _field(app.multiselect, "目标岗位方向（可多选）").set_value(["backend", "security"]).run()


def test_direction_exclusions_and_requirement_evidence_are_visible_without_blocking_eligibility(monkeypatch):
    app, _, requests = _start(monkeypatch, _quality_payload(), full_app=True)
    assert _field(app.multiselect, "目标岗位方向（可多选）").value == []
    _fill_skills(app)
    _select_targets(app)
    _recommend(app)
    assert not app.error
    assert [metric.value for metric in app.metric][:5] == ["0", "1", "0", "0", "1"]
    shown = "\n".join(item.value for item in app.text)
    assert "岗位方向 · 方向一致（后端开发）" in shown
    assert "核心技能 · 匹配 1 / 1 项" in shown and "加分技能 · 匹配 0 / 1 项" in shown
    assert "要求掌握Python" in shown and "有SQL经验者优先" in shown
    assert "岗位方向 · 方向不符（其他方向）" in shown and "实际投递条件：符合" in shown
    assert any("未分类技能 · 未识别" in item.value for item in app.caption)
    assert any("本次目标方向：后端开发、安全研发" in item.value for item in app.caption)
    assert any("方向不符的岗位（展示 1 个 / 共 1 个）" == item.label for item in app.expander)
    assert sum(item.label == "查看合并来源（2 条记录）" for item in app.expander) == 2
    post = next(request for request in requests if request.method == "POST")
    assert json.loads(post.content)["candidate"]["target_directions"] == ["backend", "security"]
    _field(app.multiselect, "目标岗位方向（可多选）").set_value(["backend"]).run()
    assert not app.metric
    assert any("上次结果已隐藏" in item.value for item in app.info)
    app.radio[0].set_value("岗位库").run()
    app.radio[0].set_value("Agent 推荐").run()
    assert _field(app.multiselect, "目标岗位方向（可多选）").value == ["backend"]
    assert len([request for request in requests if request.method == "POST"]) == 1


@pytest.mark.parametrize("with_qualification_block", [False, True])
def test_empty_filtered_page_explains_direction_and_action(monkeypatch, with_qualification_block):
    payload = _quality_payload()
    payload["recommendations"] = []
    payload["duplicate_groups"].pop(0)
    blocked = int(with_qualification_block)
    payload["counts"].update(evaluated=1 + blocked, unknown=0, returned=0, not_met=blocked)
    payload["data_scope"].update(total_records=2 + blocked, duplicate_records_collapsed=1, sample_records_excluded=0)
    if with_qualification_block:
        item = _eligibility(9, "not_met")
        item["job"]["source_url"] = "https://careers.test/jobs/9"
        payload["excluded"] = [item]
    app, _, _ = _start(monkeypatch, payload)
    _fill_skills(app)
    _select_targets(app)
    _recommend(app)
    assert not app.error
    assert any("导入相关岗位" in item.value for item in app.info)
    assert not any("均存在明确阻断" in item.value for item in app.info)
    assert any("实际投递条件：符合" in item.value for item in app.text)


def test_old_service_cannot_display_a_target_filtered_success(monkeypatch):
    app, _, requests = _start(monkeypatch)
    _fill_skills(app)
    _recommend(app)
    assert app.metric
    _select_targets(app)
    _recommend(app)
    assert not app.metric
    assert any("未返回所选岗位方向" in item.value for item in app.error)
    assert len([request for request in requests if request.method == "POST"]) == 2
