import json
from datetime import date, datetime
from typing import Any

import pytest

from app.agent.contracts import ToolCall, ToolResult
from app.agent.tools.matching_tool import (
    MatchJobsArguments,
    MatchJobsTool,
)
from app.agent.tools.registry import ToolRegistry
from app.matching.contracts import (
    CandidateProfile,
    JobMatchResult,
    MatchReason,
)
from app.matching.service import JobMatchingService
from app.schemas.job_response import JobRead


def make_result() -> JobMatchResult:
    job = JobRead(
        id=7,
        title="Python 后端实习生",
        company="示例科技",
        city="深圳",
        salary=None,
        description="负责 FastAPI 服务开发。",
        skills=["Python", "FastAPI"],
        source="mock",
        source_url="https://example.com/jobs/7",
        published_at=date(2026, 8, 1),
        created_at=datetime(2026, 8, 1, 10, 0),
    )
    return JobMatchResult(
        job=job,
        match_score=50,
        matched_skills=["Python"],
        missing_skills=["FastAPI"],
        detected_job_skills=["Python", "FastAPI"],
        reason=MatchReason.PARTIAL_MATCH,
    )


class RecordingMatchingService(JobMatchingService):
    def __init__(
        self,
        *,
        results: list[JobMatchResult] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.results = results or []
        self.error = error
        self.calls: list[tuple[CandidateProfile, int]] = []

    def match_jobs(
        self,
        *,
        candidate: CandidateProfile,
        top_k: int,
    ) -> list[JobMatchResult]:
        self.calls.append((candidate, top_k))

        if self.error is not None:
            raise self.error

        return self.results


def execute(
    tool: MatchJobsTool,
    arguments: dict[str, Any],
) -> ToolResult:
    return tool.execute(
        ToolCall(
            call_id="call_001",
            tool_name="match_jobs",
            arguments=arguments,
        )
    )


def test_match_jobs_tool_definition_uses_argument_schema() -> None:
    service = RecordingMatchingService()
    tool = MatchJobsTool(matching_service=service)

    definition = tool.definition()

    assert definition.name == "match_jobs"
    assert definition.description == (
        "Match a candidate's skills and preferred cities "
        "against stored jobs and return ranked results."
    )
    assert definition.parameters == (
        MatchJobsArguments.model_json_schema()
    )
    assert definition.parameters["required"] == ["skills"]
    assert definition.parameters["additionalProperties"] is False
    assert definition.parameters["properties"]["top_k"]["default"] == 5


def test_match_jobs_tool_delegates_normalized_candidate_and_top_k() -> None:
    expected = make_result()
    service = RecordingMatchingService(results=[expected])
    tool = MatchJobsTool(matching_service=service)

    result = execute(
        tool,
        {
            "skills": [" python ", "PYTHON", "fastapi"],
            "preferred_cities": ["深圳市", " 深圳 "],
            "top_k": 3,
        },
    )

    assert result.success is True
    assert result.error is None
    assert len(service.calls) == 1
    candidate, top_k = service.calls[0]
    assert type(candidate) is CandidateProfile
    assert candidate.skills == ["Python", "FastAPI"]
    assert candidate.preferred_cities == ["深圳"]
    assert top_k == 3
    assert result.data == [
        expected.model_dump(mode="json")
    ]


def test_match_jobs_tool_uses_optional_argument_defaults() -> None:
    service = RecordingMatchingService()
    tool = MatchJobsTool(matching_service=service)

    result = execute(
        tool,
        {"skills": ["Python"]},
    )

    assert result.success is True
    candidate, top_k = service.calls[0]
    assert candidate.preferred_cities == []
    assert top_k == 5
    assert result.data == []


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"skills": []},
        {"skills": "Python"},
        {"skills": [1]},
        {"skills": ["   "]},
        {"skills": ["Python"], "preferred_cities": "深圳"},
        {"skills": ["Python"], "preferred_cities": [1]},
        {"skills": ["Python"], "preferred_cities": ["   "]},
        {"skills": ["Python"], "top_k": True},
        {"skills": ["Python"], "top_k": 1.5},
        {"skills": ["Python"], "top_k": "5"},
        {"skills": ["Python"], "top_k": None},
        {"skills": ["Python"], "unexpected": "value"},
    ],
)
def test_match_jobs_tool_rejects_invalid_arguments_before_service(
    arguments: dict[str, Any],
) -> None:
    service = RecordingMatchingService()
    tool = MatchJobsTool(matching_service=service)

    result = execute(tool, arguments)

    assert result.success is False
    assert result.error is not None
    assert result.error.startswith("Invalid tool arguments:")
    assert service.calls == []


def test_match_jobs_tool_converts_service_exception() -> None:
    service = RecordingMatchingService(
        error=ValueError("top_k must be greater than zero."),
    )
    tool = MatchJobsTool(matching_service=service)

    result = execute(
        tool,
        {
            "skills": ["Python"],
            "top_k": 0,
        },
    )

    assert len(service.calls) == 1
    assert service.calls[0][1] == 0
    assert result.success is False
    assert result.error == "Tool execution failed."
    assert "top_k" not in result.error


def test_match_jobs_tool_returns_json_serializable_structured_results() -> None:
    service = RecordingMatchingService(results=[make_result()])
    tool = MatchJobsTool(matching_service=service)

    result = execute(
        tool,
        {"skills": ["Python"]},
    )

    assert result.success is True
    json.dumps(result.data, ensure_ascii=False)
    assert result.data[0]["job"]["published_at"] == "2026-08-01"
    assert result.data[0]["job"]["created_at"] == "2026-08-01T10:00:00"
    assert result.data[0]["reason"] == "partial_match"


def test_match_jobs_tool_registers_without_registry_changes() -> None:
    tool = MatchJobsTool(
        matching_service=RecordingMatchingService()
    )
    registry = ToolRegistry()

    registry.register(tool)

    assert registry.get("match_jobs") is tool
    assert registry.list_definitions() == [
        tool.definition()
    ]
