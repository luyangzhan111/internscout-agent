from datetime import date, datetime

from app.agent.contracts import ToolCall
from app.agent.tools.job_query import JobQueryPort
from app.agent.tools.job_tools import (
    GetJobDetailTool,
    SearchJobsTool,
)
from app.schemas.job_response import JobRead


def make_job_read(
    *,
    job_id: int = 1,
) -> JobRead:
    return JobRead(
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


class FakeJobQuery(JobQueryPort):
    """Controllable job-query fake used by Agent Tool unit tests."""

    def __init__(
        self,
        *,
        search_items: list[JobRead] | None = None,
        search_total: int = 0,
        detail_result: JobRead | None = None,
        search_error: Exception | None = None,
        detail_error: Exception | None = None,
    ) -> None:
        self.search_items = (
            search_items
            if search_items is not None
            else []
        )
        self.search_total = search_total
        self.detail_result = detail_result
        self.search_error = search_error
        self.detail_error = detail_error

        self.search_calls: list[
            dict[str, object]
        ] = []
        self.detail_calls: list[int] = []

    def search_jobs(
        self,
        *,
        city: str | None = None,
        company: str | None = None,
        skill: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[JobRead], int]:
        self.search_calls.append(
            {
                "city": city,
                "company": company,
                "skill": skill,
                "page": page,
                "page_size": page_size,
            }
        )

        if self.search_error is not None:
            raise self.search_error

        return (
            self.search_items,
            self.search_total,
        )

    def get_job_by_id(
        self,
        job_id: int,
    ) -> JobRead | None:
        self.detail_calls.append(
            job_id
        )

        if self.detail_error is not None:
            raise self.detail_error

        return self.detail_result


def test_search_jobs_tool_uses_normalized_filters_and_defaults() -> None:
    job_query = FakeJobQuery(
        search_items=[
            make_job_read()
        ],
        search_total=1,
    )

    tool = SearchJobsTool(
        job_query
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

    assert job_query.search_calls == [
        {
            "city": "深圳",
            "company": None,
            "skill": "Python Backend",
            "page": 1,
            "page_size": 10,
        }
    ]

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


def test_search_jobs_tool_returns_success_for_empty_result() -> None:
    job_query = FakeJobQuery()

    tool = SearchJobsTool(
        job_query
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


def test_search_jobs_tool_preserves_empty_high_page() -> None:
    job_query = FakeJobQuery(
        search_total=25,
    )

    tool = SearchJobsTool(
        job_query
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


def test_search_jobs_tool_rejects_blank_filter_before_query() -> None:
    job_query = FakeJobQuery()

    tool = SearchJobsTool(
        job_query
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
    assert job_query.search_calls == []


def test_search_jobs_tool_rejects_invalid_page_before_query() -> None:
    job_query = FakeJobQuery()

    tool = SearchJobsTool(
        job_query
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
    assert job_query.search_calls == []


def test_search_jobs_tool_rejects_invalid_page_size_before_query() -> None:
    job_query = FakeJobQuery()

    tool = SearchJobsTool(
        job_query
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
    assert job_query.search_calls == []


def test_search_jobs_tool_rejects_unknown_argument_before_query() -> None:
    job_query = FakeJobQuery()

    tool = SearchJobsTool(
        job_query
    )

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="search_jobs",
            arguments={
                "ctiy": "深圳",
            },
        )
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.startswith(
        "Invalid tool arguments:"
    )
    assert job_query.search_calls == []


def test_search_jobs_tool_converts_query_exception() -> None:
    job_query = FakeJobQuery(
        search_error=RuntimeError(
            "database connection failed"
        ),
    )

    tool = SearchJobsTool(
        job_query
    )

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="search_jobs",
        )
    )

    assert result.success is False
    assert result.error == (
        "Tool execution failed."
    )
    assert "database" not in result.error


def test_get_job_detail_tool_returns_job() -> None:
    job_query = FakeJobQuery(
        detail_result=make_job_read(
            job_id=3
        ),
    )

    tool = GetJobDetailTool(
        job_query
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
    assert job_query.detail_calls == [
        3
    ]

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


def test_get_job_detail_tool_returns_success_when_job_missing() -> None:
    job_query = FakeJobQuery()

    tool = GetJobDetailTool(
        job_query
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

    assert job_query.detail_calls == [
        999999
    ]


def test_get_job_detail_tool_rejects_invalid_job_id_before_query() -> None:
    job_query = FakeJobQuery()

    tool = GetJobDetailTool(
        job_query
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
    assert job_query.detail_calls == []


def test_get_job_detail_tool_rejects_unknown_argument_before_query() -> None:
    job_query = FakeJobQuery()

    tool = GetJobDetailTool(
        job_query
    )

    result = tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="get_job_detail",
            arguments={
                "job_id": 1,
                "unexpected": True,
            },
        )
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.startswith(
        "Invalid tool arguments:"
    )
    assert job_query.detail_calls == []


def test_get_job_detail_tool_converts_query_exception() -> None:
    job_query = FakeJobQuery(
        detail_error=RuntimeError(
            "database connection failed"
        ),
    )

    tool = GetJobDetailTool(
        job_query
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
    assert result.error == (
        "Tool execution failed."
    )
    assert "database" not in result.error