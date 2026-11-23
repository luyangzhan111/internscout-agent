"""User-visible HTTP failures and truthful import-result presentation."""

import json
from datetime import datetime, timezone

import httpx
import pytest

from demo.client import (
    BackendRequestError,
    BackendResponseError,
    BackendTimeoutError,
)
from demo.data_client import (
    JobDataApiClient,
    build_manual_import_payload,
    safe_http_url,
)
from demo.data_rendering import build_import_run_view, format_timestamp


def run_payload(**changes):
    result = {
        "id": 12, "source": "oppo", "status": "succeeded",
        "started_at": "2026-11-12T01:00:00",
        "finished_at": "2026-11-12T01:00:05",
        "created_count": 1, "updated_count": 2, "unchanged_count": 3,
        "failed_count": 0, "complete": True, "errors": [], "job_ids": [1, 2, 3],
    }
    result.update(changes)
    return result


def test_manual_payload_preserves_identity_and_defaults_to_unverified():
    payload = build_manual_import_payload(
        title=" 后端实习生 ", company=" 公司 ", city=" 深圳 ",
        description="第一行\n第二行", source_url=" https://example.com/jobs/1 ",
        source_job_id=" job-1 ", skills_text="Python，SQL、Python\nGit",
    )
    assert payload["jobs"] == [{
        "title": "后端实习生", "company": "公司", "city": "深圳",
        "description": "第一行\n第二行", "source_url": "https://example.com/jobs/1",
        "source_job_id": "job-1", "status": "unknown", "skills": ["Python", "SQL", "Git"],
    }]


@pytest.mark.parametrize("value", [
    "javascript:alert(1)", "data:text/html,x", "//example.com/jobs/1",
    "https://user:secret@example.com/job", "https://example.com/\njavascript:x",
    "https://example.com:invalid/job", "https://example.com\\@evil.test",
])
def test_source_links_cannot_be_unsafe_navigation(value):
    assert safe_http_url(value) is None
    with pytest.raises(ValueError, match="来源链接"):
        build_manual_import_payload(
            title="岗位", company="公司", city="深圳", description="JD",
            source_url=value,
        )


def test_listing_filters_use_http_without_agent_request():
    received = []

    def handler(request):
        received.append(request)
        return httpx.Response(200, json={
            "items": [], "total": 0, "page": 2, "page_size": 20, "pages": 0,
        })

    client = JobDataApiClient(transport=httpx.MockTransport(handler))
    result = client.list_jobs(source="manual", status="unknown", page=2)
    assert result.items == []
    assert len(received) == 1
    assert received[0].method == "GET"
    assert received[0].url.path == "/api/jobs"
    assert dict(received[0].url.params) == {
        "source": "manual", "status": "unknown", "page": "2", "page_size": "20",
    }


@pytest.mark.parametrize("status,complete,level", [
    ("partial", False, "warning"), ("failed", False, "error"),
    ("succeeded", False, "warning"), ("succeeded", True, "success"),
])
def test_http_success_preserves_actual_run_outcome(status, complete, level):
    received = []

    def handler(request):
        received.append(request)
        return httpx.Response(200, json=run_payload(status=status, complete=complete))

    client = JobDataApiClient(transport=httpx.MockTransport(handler))
    run = client.refresh_oppo(keyword=" Python ", max_pages=1, max_jobs=5)
    assert received[0].url.path == "/api/imports/oppo"
    assert json.loads(received[0].content) == {"keyword": "Python", "max_pages": 1, "max_jobs": 5}
    view = build_import_run_view(run)
    assert view.level == level
    assert "新增 1 · 更新 2 · 未变化 3 · 失败 0" == view.counts
    if not complete:
        assert view.note is not None


def test_history_accepts_running_operations_without_marking_them_failed():
    client = JobDataApiClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=[run_payload(
            status="running", complete=False, finished_at=None,
        )])
    ))
    run = client.list_imports()[0]
    view = build_import_run_view(run)
    assert view.level == "info"
    assert "仍在进行" in view.title
    assert "避免重复提交" in view.note


def test_manual_import_posts_payload_and_keeps_failed_items_visible():
    received = []

    def handler(request):
        received.append(request)
        return httpx.Response(200, json=run_payload(
            source="manual", status="partial", complete=False, failed_count=1,
            errors=[{"item_id": "job-2", "message": "无法保存"}],
        ))

    client = JobDataApiClient(transport=httpx.MockTransport(handler))
    payload = {"jobs": [{"title": "岗位"}]}
    run = client.import_manual(payload)
    assert received[0].url.path == "/api/imports/manual"
    assert json.loads(received[0].content) == payload
    assert build_import_run_view(run).errors == ("job-2：无法保存",)


def test_post_timeout_does_not_retry_and_directs_user_to_history():
    requests = []

    def handler(request):
        requests.append(request)
        raise httpx.ReadTimeout("timed out", request=request)

    client = JobDataApiClient(transport=httpx.MockTransport(handler))
    with pytest.raises(BackendTimeoutError, match="查看近期记录"):
        client.refresh_oppo()
    assert len(requests) == 1


@pytest.mark.parametrize("status,payload,error", [
    (422, {"detail": [{"msg": "too long"}]}, BackendRequestError),
    (200, {"unexpected": "shape"}, BackendResponseError),
])
def test_unreadable_or_rejected_responses_are_user_visible(status, payload, error):
    client = JobDataApiClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, json=payload)
    ))
    with pytest.raises(error):
        client.list_jobs()


def test_api_utc_timestamps_are_displayed_in_beijing_time():
    expected = "2026-11-12 09:00（北京时间）"
    assert format_timestamp(datetime(2026, 11, 12, 1)) == expected
    assert format_timestamp(datetime(2026, 11, 12, 1, tzinfo=timezone.utc)) == expected
    assert format_timestamp(None) == "尚无记录"
