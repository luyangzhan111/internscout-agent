from datetime import date, datetime
from types import SimpleNamespace
from typing import Any

from app.agent.contracts import ToolCall
from app.agent.tools import job_tools
from app.agent.tools.job_tools import (
    GetJobDetailTool,
    SearchJobsTool,
)


def make_job_record(
    *,
    job_id: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=job_id,
        title="AI 应用开发实习生",
        company="示例科技",
        city="深圳",
        salary="200-300/天",
        description="参与 AI Agent 应用开发。",
        skills=[
            "python",
            "fastapi",
        ],
        source="mock",
        source_url=(
            "https://example.com/jobs/1"
        ),
        published_at=date(
            2026,
            8,
            1,
        ),
        created_at=datetime(
            2026,
            8,
            1,
            10,
            30,
            0,
        ),
    )


def test_search_jobs_tool_uses_normalized_filters_and_defaults(
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}
    session = object()

    def fake_query_jobs(
        received_session: object,
        **kwargs: Any,
    ) -> tuple[list[SimpleNamespace], int]:
        captured["session"] = received_session
        captured.update(kwargs)

        return [
            make_job_record()
        ], 1

    monkeypatch.setattr(
        job_tools,
        "query_jobs",
        fake_query_jobs,
    )

    tool = SearchJobsTool(
        session  # type: ignore[arg-type]
    )

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="search_jobs",
            arguments={
                "city": "   深圳   ",
                "skill": " Python    Backend ",
            },
        )
    )

    assert result.success is True
    assert captured["session"] is session
    assert captured["city"] == "深圳"
    assert captured["company"] is None
    assert captured["skill"] == "Python Backend"
    assert captured["page"] == 1
    assert captured["page_size"] == 10

    assert result.data is not None
    assert result.data["total"] == 1
    assert result.data["page"] == 1
    assert result.data["page_size"] == 10
    assert result.data["pages"] == 1

    assert result.data["items"][0]["id"] == 1
    assert (
        result.data["items"][0]["published_at"]
        == "2026-08-01"
    )
    assert (
        result.data["items"][0]["created_at"]
        == "2026-08-01T10:30:00"
    )


def test_search_jobs_tool_returns_success_for_empty_result(
    monkeypatch: Any,
) -> None:
    def fake_query_jobs(
        session: object,
        **kwargs: Any,
    ) -> tuple[list[SimpleNamespace], int]:
        return [], 0

    monkeypatch.setattr(
        job_tools,
        "query_jobs",
        fake_query_jobs,
    )

    tool = SearchJobsTool(
        object()  # type: ignore[arg-type]
    )

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="search_jobs",
        )
    )

    assert result.success is True
    assert result.data == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 10,
        "pages": 0,
    }


def test_search_jobs_tool_preserves_empty_high_page(
    monkeypatch: Any,
) -> None:
    def fake_query_jobs(
        session: object,
        **kwargs: Any,
    ) -> tuple[list[SimpleNamespace], int]:
        return [], 25

    monkeypatch.setattr(
        job_tools,
        "query_jobs",
        fake_query_jobs,
    )

    tool = SearchJobsTool(
        object()  # type: ignore[arg-type]
    )

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="search_jobs",
            arguments={
                "page": 999,
                "page_size": 10,
            },
        )
    )

    assert result.success is True
    assert result.data == {
        "items": [],
        "total": 25,
        "page": 999,
        "page_size": 10,
        "pages": 3,
    }


def test_search_jobs_tool_rejects_blank_filter_before_repository(
    monkeypatch: Any,
) -> None:
    called = False

    def fake_query_jobs(
        session: object,
        **kwargs: Any,
    ) -> tuple[list[SimpleNamespace], int]:
        nonlocal called
        called = True

        return [], 0

    monkeypatch.setattr(
        job_tools,
        "query_jobs",
        fake_query_jobs,
    )

    tool = SearchJobsTool(
        object()  # type: ignore[arg-type]
    )

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="search_jobs",
            arguments={
                "city": "     ",
            },
        )
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.startswith(
        "Invalid tool arguments:"
    )
    assert called is False


def test_search_jobs_tool_rejects_invalid_page_before_repository(
    monkeypatch: Any,
) -> None:
    called = False

    def fake_query_jobs(
        session: object,
        **kwargs: Any,
    ) -> tuple[list[SimpleNamespace], int]:
        nonlocal called
        called = True

        return [], 0

    monkeypatch.setattr(
        job_tools,
        "query_jobs",
        fake_query_jobs,
    )

    tool = SearchJobsTool(
        object()  # type: ignore[arg-type]
    )

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="search_jobs",
            arguments={
                "page": 0,
            },
        )
    )

    assert result.success is False
    assert called is False


def test_search_jobs_tool_rejects_invalid_page_size_before_repository(
    monkeypatch: Any,
) -> None:
    called = False

    def fake_query_jobs(
        session: object,
        **kwargs: Any,
    ) -> tuple[list[SimpleNamespace], int]:
        nonlocal called
        called = True

        return [], 0

    monkeypatch.setattr(
        job_tools,
        "query_jobs",
        fake_query_jobs,
    )

    tool = SearchJobsTool(
        object()  # type: ignore[arg-type]
    )

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="search_jobs",
            arguments={
                "page_size": 101,
            },
        )
    )

    assert result.success is False
    assert called is False


def test_search_jobs_tool_converts_repository_exception(
    monkeypatch: Any,
) -> None:
    def fake_query_jobs(
        session: object,
        **kwargs: Any,
    ) -> tuple[list[SimpleNamespace], int]:
        raise RuntimeError(
            "database connection failed"
        )

    monkeypatch.setattr(
        job_tools,
        "query_jobs",
        fake_query_jobs,
    )

    tool = SearchJobsTool(
        object()  # type: ignore[arg-type]
    )

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="search_jobs",
        )
    )

    assert result.success is False
    assert result.error == "Tool execution failed."
    assert "database" not in result.error


def test_get_job_detail_tool_returns_job(
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}
    session = object()

    def fake_get_job_by_id(
        received_session: object,
        job_id: int,
    ) -> SimpleNamespace:
        captured["session"] = received_session
        captured["job_id"] = job_id

        return make_job_record(
            job_id=3
        )

    monkeypatch.setattr(
        job_tools,
        "get_job_by_id",
        fake_get_job_by_id,
    )

    tool = GetJobDetailTool(
        session  # type: ignore[arg-type]
    )

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="get_job_detail",
            arguments={
                "job_id": 3,
            },
        )
    )

    assert result.success is True
    assert captured == {
        "session": session,
        "job_id": 3,
    }

    assert result.data is not None
    assert result.data["id"] == 3
    assert (
        result.data["title"]
        == "AI 应用开发实习生"
    )
    assert (
        result.data["published_at"]
        == "2026-08-01"
    )


def test_get_job_detail_tool_returns_success_when_job_missing(
    monkeypatch: Any,
) -> None:
    def fake_get_job_by_id(
        session: object,
        job_id: int,
    ) -> None:
        return None

    monkeypatch.setattr(
        job_tools,
        "get_job_by_id",
        fake_get_job_by_id,
    )

    tool = GetJobDetailTool(
        object()  # type: ignore[arg-type]
    )

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="get_job_detail",
            arguments={
                "job_id": 999999,
            },
        )
    )

    assert result.success is True
    assert result.data is None
    assert result.error is None


def test_get_job_detail_tool_rejects_invalid_job_id_before_repository(
    monkeypatch: Any,
) -> None:
    called = False

    def fake_get_job_by_id(
        session: object,
        job_id: int,
    ) -> None:
        nonlocal called
        called = True

        return None

    monkeypatch.setattr(
        job_tools,
        "get_job_by_id",
        fake_get_job_by_id,
    )

    tool = GetJobDetailTool(
        object()  # type: ignore[arg-type]
    )

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="get_job_detail",
            arguments={
                "job_id": 0,
            },
        )
    )

    assert result.success is False
    assert called is False


def test_get_job_detail_tool_converts_repository_exception(
    monkeypatch: Any,
) -> None:
    def fake_get_job_by_id(
        session: object,
        job_id: int,
    ) -> None:
        raise RuntimeError(
            "database connection failed"
        )

    monkeypatch.setattr(
        job_tools,
        "get_job_by_id",
        fake_get_job_by_id,
    )

    tool = GetJobDetailTool(
        object()  # type: ignore[arg-type]
    )

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="get_job_detail",
            arguments={
                "job_id": 1,
            },
        )
    )

    assert result.success is False
    assert result.error == "Tool execution failed."
    assert "database" not in result.error