"""Tests for the Streamlit-to-FastAPI HTTP client."""

import json
from typing import Any

import httpx
import pytest

from demo.client import (
    AgentApiClient,
    BackendRequestError,
    BackendResponseError,
    BackendTimeoutError,
    BackendUnavailableError,
    build_query_payload,
)


def response_payload() -> dict[str, Any]:
    return {
        "answer": "已找到匹配岗位。",
        "steps": 2,
        "tool_execution_count": 1,
        "recommendations": [
            {
                "job": {
                    "id": 1,
                    "title": "Python后端实习生",
                    "company": "星河科技",
                    "city": "深圳",
                    "salary": "150-200元/天",
                    "description": "负责后端开发。",
                    "skills": ["Python", "FastAPI"],
                    "source": "test",
                    "source_url": "https://example.com/jobs/1",
                    "published_at": "2026-08-10",
                    "created_at": "2026-08-10T00:00:00Z",
                },
                "match_score": 50,
                "matched_skills": ["Python"],
                "missing_skills": ["FastAPI"],
                "detected_job_skills": ["Python", "FastAPI"],
                "reason": "partial_match",
            }
        ],
    }


def test_build_query_payload_opts_into_structured_recommendations() -> None:
    assert build_query_payload("  匹配岗位  ") == {
        "user_message": "匹配岗位",
        "include_recommendations": True,
    }


def test_build_query_payload_rejects_blank_message() -> None:
    with pytest.raises(ValueError, match="cannot be blank"):
        build_query_payload("   ")


def test_client_posts_expected_request_and_parses_response() -> None:
    received: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received["method"] = request.method
        received["path"] = request.url.path
        received["payload"] = json.loads(request.content)
        return httpx.Response(200, json=response_payload())

    client = AgentApiClient(
        base_url="http://backend.test/",
        transport=httpx.MockTransport(handler),
    )

    response = client.query("匹配深圳的 Python 岗位")

    assert received == {
        "method": "POST",
        "path": "/api/agent/query",
        "payload": {
            "user_message": "匹配深圳的 Python 岗位",
            "include_recommendations": True,
        },
    }
    assert response.answer == "已找到匹配岗位。"
    assert response.recommendations is not None
    assert response.recommendations[0].match_score == 50


def test_client_translates_timeout_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(
            "timed out",
            request=request,
        )

    client = AgentApiClient(
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(BackendTimeoutError):
        client.query("匹配岗位")


def test_client_translates_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "offline",
            request=request,
        )

    client = AgentApiClient(
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(BackendUnavailableError):
        client.query("匹配岗位")


def test_client_translates_backend_request_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={"detail": "请求参数无效。"},
        )

    client = AgentApiClient(
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        BackendRequestError,
        match="请求参数无效",
    ):
        client.query("匹配岗位")


def test_client_rejects_invalid_backend_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"answer": "缺少字段"},
        )

    client = AgentApiClient(
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(BackendResponseError):
        client.query("匹配岗位")
