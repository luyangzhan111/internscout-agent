"""Exercise the visible model-independent flow against a mocked HTTP service."""

import json
from pathlib import Path

import httpx
from streamlit.testing.v1 import AppTest

from demo.data_client import JobDataApiClient


APP_PATH = Path(__file__).resolve().parents[2] / "demo" / "app.py"


def test_empty_library_offers_real_import_and_opt_in_demo_data(monkeypatch):
    requests = []
    sample = {
        "id": 1, "title": "Python 后端实习样例", "company": "示例公司",
        "city": "深圳", "description": "参与 Python 后端开发",
        "source": "mock", "source_url": "https://example.com/jobs/1",
        "status": "unknown",
    }

    def handler(request):
        method_path = (request.method, request.url.path)
        requests.append(method_path)
        if method_path == ("GET", "/api/jobs"):
            items = [sample] if ("POST", "/api/crawl") in requests else []
            return httpx.Response(200, json={
                "items": items, "total": len(items), "page": 1, "page_size": 20, "pages": len(items),
            })
        if method_path == ("GET", "/api/imports"):
            return httpx.Response(200, json=[])
        assert method_path == ("POST", "/api/crawl")
        return httpx.Response(200, json={"processed_count": 1, "database_total": 1})

    client = JobDataApiClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(JobDataApiClient, "from_env", lambda: client)
    app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    assert not app.exception
    assert any("无需 API 密钥" in item.value for item in app.info)
    next(button for button in app.button if button.label == "导入真实岗位").click().run()
    assert not app.exception
    assert app.radio[0].value == "导入与更新"
    assert any(widget.label == "岗位原文 *" for widget in app.text_area)
    assert not any(method == "POST" for method, _ in requests)

    app.radio[0].set_value("岗位库").run()
    next(button for button in app.button if button.label == "加载演示岗位").click().run()
    assert not app.exception
    assert [path for method, path in requests if method == "POST"] == ["/api/crawl"]
    assert any("仅用于演示" in item.value for item in app.warning)
    assert any("包含演示数据（仅用于体验）" in item.value for item in app.caption)
    assert any(sample["title"] in item.value for item in app.markdown)


def test_library_and_manual_import_work_without_model_configuration(monkeypatch):
    requests = []
    runs = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/api/jobs":
            return httpx.Response(200, json={
                "items": [{
                    "id": 1, "title": "样例岗位", "company": "示例公司",
                    "city": "深圳", "description": "此岗位仅供演示",
                    "source": "mock", "source_url": "javascript:alert(1)",
                    "status": "unknown",
                }], "total": 1, "page": 1, "page_size": 20, "pages": 1,
            })
        if request.url.path == "/api/imports/manual":
            run = {
                "id": 1, "source": "manual", "status": "succeeded",
                "started_at": "2026-11-12T01:00:00", "finished_at": "2026-11-12T01:00:01",
                "created_count": 1, "updated_count": 0, "unchanged_count": 0,
                "failed_count": 0, "complete": True, "errors": [], "job_ids": [2],
            }
            runs.append(run)
            return httpx.Response(200, json=run)
        if request.url.path == "/api/imports":
            return httpx.Response(200, json=runs)
        raise AssertionError(f"Unexpected request: {request.url}")

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    client = JobDataApiClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(JobDataApiClient, "from_env", lambda: client)
    app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    assert not app.exception
    assert any("样例数据" in item.value for item in app.warning)
    assert any("待确认" in item.value for item in app.markdown)
    assert not app.get("link_button")

    app.radio[0].set_value("导入与更新").run()
    assert not app.exception
    values = {
        "岗位名称 *": "Python 实习生", "公司 *": "示例公司", "城市 *": "深圳",
        "岗位来源链接 *": "https://example.com/jobs/2",
        "来源岗位 ID（可选）": "original-2",
    }
    for widget in app.text_input:
        if widget.label in values:
            widget.set_value(values[widget.label])
    app.text_area[0].set_value("参与 Python 后端开发")
    next(button for button in app.button if button.label == "保存 / 更新岗位").click().run()
    assert not app.exception
    assert any("已完成" in item.value for item in app.success)
    posted = [request for request in requests if request.method == "POST"]
    assert len(posted) == 1
    job = json.loads(posted[0].content)["jobs"][0]
    assert job["status"] == "unknown"
    assert job["source_job_id"] == "original-2"
    assert not any(request.url.path.startswith("/api/agent") for request in requests)


def test_oppo_partial_result_is_a_warning_in_the_page(monkeypatch):
    run = {
        "id": 2, "source": "oppo", "status": "partial",
        "started_at": "2026-11-12T01:00:00", "finished_at": "2026-11-12T01:00:01",
        "created_count": 2, "updated_count": 0, "unchanged_count": 0,
        "failed_count": 0, "complete": False,
        "errors": [], "warnings": ["已达到本次岗位数量上限"], "job_ids": [3, 4],
    }
    client = JobDataApiClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=(
            run if request.method == "POST" else []
        ))
    ))
    monkeypatch.setattr(JobDataApiClient, "from_env", lambda: client)
    app = AppTest.from_string(
        "from demo.data_page import render_imports\nrender_imports()", default_timeout=10
    ).run()
    next(button for button in app.button if button.label == "从 OPPO 官网刷新").click().run()
    assert not app.exception
    assert any("部分完成" in item.value for item in app.warning)
    assert not app.success
    assert any("岗位数量上限" in item.value for item in app.text)
    assert any("新增 2 · 更新 0 · 未变化 0 · 失败 0" in item.value for item in app.markdown)
