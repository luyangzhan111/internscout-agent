"""Exercise current-page scope and stale-result removal without a real server."""

import copy
import json
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from demo.data_client import JobDataApiClient
from demo.eligibility_client import EligibilityApiClient


APP_PATH = Path(__file__).resolve().parents[2] / "demo" / "app.py"


def _job():
    return {
        "id": 7, "title": "开发实习生", "company": "示例公司", "city": "深圳",
        "description": "2027届，本科及以上，经验不限，至少实习6个月。<b>原文</b>",
        "source": "manual", "source_url": "https://example.com/jobs/7",
        "status": "unknown", "updated_at": "2026-11-12T01:00:00",
    }


def _result(job):
    return {
        "job": copy.deepcopy(job), "overall": "unknown", "reason": "尚有条件需要核实",
        "checks": [{
            "dimension": dimension, "status": "unknown", "reason": "候选人信息未提供",
            "candidate_value": "未填写", "requirement": "待核对",
            "evidence": [{"field": "description", "text": job["description"], "start": 0, "end": len(job["description"])}],
            "notes": ["硕士优先，仅作偏好"],
        } for dimension in ("graduation_year", "degree", "experience", "city", "internship_duration")],
        "blocking_reasons": [], "source_fingerprint": "test", "rules_version": "test-v1",
    }


def _start(monkeypatch, *, full_app=False):
    state = {"jobs": [_job()], "list_fails": False, "response_job": None, "check_updates": []}
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/api/jobs":
            if state["list_fails"]:
                return httpx.Response(500, json={"detail": "offline"})
            return httpx.Response(200, json={
                "items": state["jobs"], "total": 25, "page": int(request.url.params["page"]),
                "page_size": 20, "pages": 2,
            })
        if request.url.path == "/api/eligibility/evaluate":
            jobs = [state["response_job"]] if state["response_job"] else state["jobs"]
            items = [_result(job) for job in jobs]
            for result in items:
                for check, updates in zip(result["checks"], state["check_updates"]):
                    check.update(updates)
            return httpx.Response(200, json={
                "items": items, "assessed_at": "2026-11-12T01:00:00",
            })
        raise AssertionError(f"Unexpected endpoint {request.url.path}")

    transport = httpx.MockTransport(handler)
    data_client = JobDataApiClient(transport=transport)
    eligibility_client = EligibilityApiClient(transport=transport)
    monkeypatch.setattr(JobDataApiClient, "from_env", lambda: data_client)
    monkeypatch.setattr(EligibilityApiClient, "from_env", lambda: eligibility_client)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    if full_app:
        app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        app.radio[0].set_value("投递条件").run()
    else:
        app = AppTest.from_string(
            "from demo.eligibility_page import render_eligibility\nrender_eligibility()",
            default_timeout=10,
        ).run()
    assert not app.exception
    return app, state, requests


def _widget(widgets, label):
    return next(widget for widget in widgets if widget.label == label)


def _evaluate(app):
    next(button for button in app.button if button.label.startswith("判断当前页")).click().run()
    assert not app.exception


def test_current_page_only_blank_input_and_plain_text_evidence(monkeypatch):
    app, _, requests = _start(monkeypatch, full_app=True)
    assert not app.metric
    _evaluate(app)
    payload = json.loads(next(request.content for request in requests if request.method == "POST"))
    assert payload["job_ids"] == [7]
    assert all(value is None for value in payload["profile"].values())
    assert [metric.value for metric in app.metric] == ["0", "0", "1"]
    assert any("当前页 1 个岗位" in item.value for item in app.caption)
    assert any("<b>原文</b>" in item.value for item in app.text)
    assert not any("<b>原文</b>" in item.value for item in app.markdown)
    assert any("硕士优先，仅作偏好" in item.value for item in app.text)
    link, = app.get("link_button")
    assert link.proto.label == "前往岗位来源核对"
    assert link.proto.url == _job()["source_url"]
    assert all(request.url.path in {"/api/jobs", "/api/eligibility/evaluate"} for request in requests)


def test_zero_and_unrestricted_cities_reach_api_and_draft_survives_navigation(monkeypatch):
    app, _, requests = _start(monkeypatch, full_app=True)
    _widget(app.text_input, "正式工作经验（月，可选）").set_value("0").run()
    _widget(app.selectbox, "可接受的城市").set_value("unrestricted").run()
    _evaluate(app)
    payload = json.loads([request for request in requests if request.method == "POST"][-1].content)
    assert payload["profile"]["work_experience_months"] == 0
    assert payload["profile"]["acceptable_cities"] == []
    app.radio[0].set_value("岗位库").run()
    app.radio[0].set_value("投递条件").run()
    assert not app.exception
    assert _widget(app.text_input, "正式工作经验（月，可选）").value == "0"
    assert _widget(app.selectbox, "可接受的城市").value == "unrestricted"


@pytest.mark.parametrize("change", ["candidate", "invalid_candidate", "source", "status", "page"])
def test_input_or_scope_changes_hide_old_results_without_new_post(monkeypatch, change):
    app, _, requests = _start(monkeypatch)
    _evaluate(app)
    assert len(app.metric) == 3
    if change in {"candidate", "invalid_candidate"}:
        _widget(app.text_input, "毕业年份（可选）").set_value("2027" if change == "candidate" else "invalid").run()
    elif change == "source":
        _widget(app.selectbox, "岗位来源").set_value("manual").run()
    elif change == "status":
        _widget(app.selectbox, "招聘状态").set_value("unknown").run()
    elif change == "page":
        _widget(app.number_input, "岗位页码").set_value(2).run()
    assert not app.exception
    assert not app.metric
    assert any("上次判断已隐藏" in item.value for item in app.info)
    assert len([request for request in requests if request.method == "POST"]) == 1


def test_updated_source_text_hides_previous_decision(monkeypatch):
    app, state, _ = _start(monkeypatch)
    _evaluate(app)
    state["jobs"][0]["description"] = "新的岗位原文：仅限2026届"
    app.run()
    assert not app.exception
    assert not app.metric
    assert any("上次判断已隐藏" in item.value for item in app.info)


def test_job_change_between_listing_and_evaluation_never_shows_old_decision(monkeypatch):
    app, state, _ = _start(monkeypatch)
    state["response_job"] = dict(_job(), status="closed")
    _evaluate(app)
    assert not app.metric
    assert any("本次结果已隐藏" in item.value for item in app.warning)


def test_failed_current_job_fetch_removes_old_results(monkeypatch):
    app, state, _ = _start(monkeypatch)
    _evaluate(app)
    state["list_fails"] = True
    app.run()
    assert not app.exception
    assert not app.metric
    assert app.error


def test_selected_but_empty_cities_cannot_be_submitted_as_unrestricted(monkeypatch):
    app, _, requests = _start(monkeypatch)
    _widget(app.selectbox, "可接受的城市").set_value("selected").run()
    _evaluate(app)
    assert not any(request.method == "POST" for request in requests)
    assert any("至少填写一个" in item.value for item in app.error)
    assert not app.metric


def test_standalone_conditions_show_explicit_unknown_causes_and_next_steps(monkeypatch):
    app, state, _ = _start(monkeypatch)
    categories = [
        ("candidate_missing", "个人信息缺失"), ("source_unspecified", "原文未说明"),
        ("interpretation_uncertain", "无法可靠判断"), ("requirements_conflict", "要求冲突"),
    ]
    state["check_updates"] = [
        {"unknown_reason": category, "next_step": "请核对 <b>岗位信息</b>"}
        for category, _ in categories
    ]
    _evaluate(app)
    captions = "\n".join(item.value for item in app.caption)
    for _, label in categories:
        assert f"待确认类型：{label}" in captions
    assert any("下一步：请核对 <b>岗位信息</b>" == item.value for item in app.text)
    assert not any("<b>岗位信息</b>" in item.value for item in app.markdown)


def test_old_cached_checks_without_categories_do_not_invent_guidance(monkeypatch):
    app, _, requests = _start(monkeypatch)
    _evaluate(app)
    response = app.session_state["eligibility_current_result"]["response"]
    for check in response.items[0].checks:
        check.__dict__.pop("unknown_reason", None)
        check.__dict__.pop("next_step", None)
    app.run()
    assert not app.exception
    assert any("候选人信息未提供" in item.value for item in app.text)
    assert not any("待确认类型" in item.value for item in app.caption)
    assert not any("下一步：" in item.value for item in app.text)
    assert len([request for request in requests if request.method == "POST"]) == 1
