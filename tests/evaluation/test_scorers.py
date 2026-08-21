import pytest

from app.agent.contracts import (
    AgentResult,
    ToolCall,
    ToolExecution,
    ToolResult,
)
from evals.contracts import (
    EvalCase,
    EvaluationCaseResult,
    EvaluationRunResult,
)
from evals.scorers import (
    score_answer_facts,
    score_case,
    score_execution_outcome,
    score_run,
    score_tool_arguments,
    score_tool_results,
    score_tool_selection,
    score_tool_sequence,
)


def make_case(
    *,
    case_id: str = "synthetic_case",
    outcome: str = "success",
    tool_calls: list[dict[str, object]] | None = None,
    tool_results: list[dict[str, object]] | None = None,
    answer_contains: list[str] | None = None,
    answer_excludes: list[str] | None = None,
) -> EvalCase:
    calls = tool_calls or []
    results = tool_results or []
    return EvalCase.model_validate(
        {
            "schema_version": 1,
            "case_id": case_id,
            "category": "failure" if outcome == "controlled_failure" else "search_jobs",
            "description": "Synthetic scorer case.",
            "user_message": "执行测试。",
            "expected": {
                "outcome": outcome,
                "tool_sequence": [call["tool_name"] for call in calls],
                "tool_calls": calls,
                "tool_results": results,
                "answer": {
                    "contains": answer_contains or [],
                    "excludes": answer_excludes or [],
                },
            },
        }
    )


def make_execution(
    tool_name: str,
    arguments: dict[str, object] | None = None,
    *,
    success: bool = True,
    data: object = None,
    error: str | None = None,
    call_id: str = "call-1",
) -> ToolExecution:
    return ToolExecution(
        call=ToolCall(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments or {},
        ),
        result=ToolResult(
            call_id=call_id,
            tool_name=tool_name,
            success=success,
            data=data,
            error=error,
        ),
    )


def make_result(
    *,
    answer: str = "完成。",
    executions: list[ToolExecution] | None = None,
    case_id: str = "synthetic_case",
    status: str = "completed",
) -> EvaluationCaseResult:
    return EvaluationCaseResult(
        case_id=case_id,
        status=status,
        agent_result=(
            AgentResult(
                answer=answer,
                tool_executions=executions or [],
                steps=len(executions or []) + 1,
            )
            if status == "completed"
            else None
        ),
        error_type=None if status == "completed" else "SyntheticFailure",
        error_message=None if status == "completed" else "failed",
    )


def test_correct_tool_selection() -> None:
    case = make_case(
        tool_calls=[{"tool_name": "search_jobs", "arguments": {}}],
    )
    result = make_result(
        executions=[make_execution("search_jobs")],
    )

    assert score_tool_selection(case, result).passed


def test_wrong_tool_selection_detects_missing_and_unexpected_tool() -> None:
    case = make_case(
        tool_calls=[{"tool_name": "search_jobs", "arguments": {}}],
    )
    result = make_result(
        executions=[make_execution("get_job_detail")],
    )

    metric = score_tool_selection(case, result)
    assert not metric.passed
    assert "search_jobs" in metric.reason
    assert "get_job_detail" in metric.reason


def test_multi_tool_sequence_order_mismatch() -> None:
    case = make_case(
        tool_calls=[
            {"tool_name": "search_jobs", "arguments": {}},
            {"tool_name": "get_job_detail", "arguments": {}},
        ],
    )
    result = make_result(
        executions=[
            make_execution("get_job_detail", call_id="call-1"),
            make_execution("search_jobs", call_id="call-2"),
        ],
    )

    metric = score_tool_sequence(case, result)
    assert not metric.passed
    assert metric.expected != metric.actual


@pytest.mark.parametrize(
    "actual_arguments, expected_fragment",
    [
        ({}, "missing key"),
        ({"city": "深圳", "extra": True}, "unexpected key"),
    ],
)
def test_argument_missing_or_extra_field_fails(
    actual_arguments: dict[str, object],
    expected_fragment: str,
) -> None:
    case = make_case(
        tool_calls=[
            {
                "tool_name": "search_jobs",
                "arguments": {"city": "深圳"},
            }
        ],
    )
    result = make_result(
        executions=[make_execution("search_jobs", actual_arguments)],
    )

    metric = score_tool_arguments(case, result)
    assert not metric.passed
    assert expected_fragment in metric.reason


def test_none_and_missing_argument_field_are_not_equal() -> None:
    case = make_case(
        tool_calls=[
            {
                "tool_name": "search_jobs",
                "arguments": {"city": None},
            }
        ],
    )
    result = make_result(
        executions=[make_execution("search_jobs")],
    )

    metric = score_tool_arguments(case, result)
    assert not metric.passed
    assert "missing key" in metric.reason


def test_argument_list_order_is_strict() -> None:
    case = make_case(
        tool_calls=[
            {
                "tool_name": "match_jobs",
                "arguments": {"skills": ["Python", "SQL"]},
            }
        ],
    )
    result = make_result(
        executions=[
            make_execution(
                "match_jobs",
                {"skills": ["SQL", "Python"]},
            )
        ],
    )

    metric = score_tool_arguments(case, result)
    assert not metric.passed
    assert "[0]" in metric.reason


def test_nested_and_list_index_path_resolution() -> None:
    case = make_case(
        tool_calls=[{"tool_name": "search_jobs", "arguments": {}}],
        tool_results=[
            {
                "tool_name": "search_jobs",
                "success": True,
                "data_assertions": [
                    {"path": "items[0].job.city", "equals": "深圳"},
                    {"path": "items[0].skills", "contains": "Python"},
                ],
            }
        ],
    )
    result = make_result(
        executions=[
            make_execution(
                "search_jobs",
                data={
                    "items": [
                        {"job": {"city": "深圳"}, "skills": ["Python"]}
                    ]
                },
            )
        ],
    )

    metric = score_tool_results(case, result)
    assert metric.passed


def test_root_dollar_assertion() -> None:
    case = make_case(
        tool_calls=[{"tool_name": "get_job_detail", "arguments": {}}],
        tool_results=[
            {
                "tool_name": "get_job_detail",
                "success": True,
                "data_assertions": [{"path": "$", "equals": None}],
            }
        ],
    )
    result = make_result(
        executions=[make_execution("get_job_detail", data=None)],
    )

    assert score_tool_results(case, result).passed


def test_missing_data_path_fails_explicitly() -> None:
    case = make_case(
        tool_calls=[{"tool_name": "search_jobs", "arguments": {}}],
        tool_results=[
            {
                "tool_name": "search_jobs",
                "success": True,
                "data_assertions": [{"path": "missing", "equals": 1}],
            }
        ],
    )
    result = make_result(
        executions=[make_execution("search_jobs", data={"total": 1})],
    )

    metric = score_tool_results(case, result)
    assert not metric.passed
    assert "does not resolve" in metric.reason


def test_equals_assertion_is_strict() -> None:
    case = make_case(
        tool_calls=[{"tool_name": "search_jobs", "arguments": {}}],
        tool_results=[
            {
                "tool_name": "search_jobs",
                "success": True,
                "data_assertions": [{"path": "total", "equals": 1}],
            }
        ],
    )
    result = make_result(
        executions=[make_execution("search_jobs", data={"total": "1"})],
    )

    metric = score_tool_results(case, result)
    assert not metric.passed
    assert "expected type int" in metric.reason


def test_contains_string_and_list() -> None:
    case = make_case(
        tool_calls=[{"tool_name": "search_jobs", "arguments": {}}],
        tool_results=[
            {
                "tool_name": "search_jobs",
                "success": True,
                "data_assertions": [
                    {"path": "message", "contains": "深圳"},
                    {"path": "skills", "contains": ["Python", "SQL"]},
                ],
            }
        ],
    )
    result = make_result(
        executions=[
            make_execution(
                "search_jobs",
                data={
                    "message": "已找到深圳岗位",
                    "skills": ["Python", "FastAPI", "SQL"],
                },
            )
        ],
    )

    assert score_tool_results(case, result).passed


def test_successful_tool_result_is_scored() -> None:
    case = make_case(
        tool_calls=[{"tool_name": "search_jobs", "arguments": {}}],
        tool_results=[
            {"tool_name": "search_jobs", "success": True}
        ],
    )
    result = make_result(
        executions=[make_execution("search_jobs", success=True)],
    )

    assert score_tool_results(case, result).passed


def test_expected_controlled_tool_failure_is_not_runner_failure() -> None:
    case = make_case(
        outcome="controlled_failure",
        tool_calls=[
            {"tool_name": "search_jobs", "arguments": {"page": 0}}
        ],
        tool_results=[
            {
                "tool_name": "search_jobs",
                "success": False,
                "error_contains": ["Invalid tool arguments"],
            }
        ],
        answer_contains=["参数无效"],
    )
    result = make_result(
        answer="参数无效，未执行查询。",
        executions=[
            make_execution(
                "search_jobs",
                {"page": 0},
                success=False,
                error="Invalid tool arguments: page must be positive",
            )
        ],
    )

    assert score_execution_outcome(case, result).passed
    assert score_case(case, result).passed


def test_unexpected_tool_failure_fails_success_case() -> None:
    case = make_case(
        tool_calls=[{"tool_name": "search_jobs", "arguments": {}}],
        tool_results=[
            {"tool_name": "search_jobs", "success": True}
        ],
    )
    result = make_result(
        executions=[
            make_execution(
                "search_jobs",
                success=False,
                error="Tool execution failed.",
            )
        ],
    )

    metric = score_tool_results(case, result)
    assert not metric.passed
    assert score_case(case, result).status == "FAIL"


def test_answer_contains_and_excludes() -> None:
    case = make_case(
        answer_contains=["Python"],
        answer_excludes=["失败"],
    )

    assert score_answer_facts(
        case,
        make_result(answer="找到 Python 岗位。"),
    ).passed
    assert not score_answer_facts(
        case,
        make_result(answer="Python 查询失败。"),
    ).passed


def test_answer_unicode_whitespace_and_case_normalization() -> None:
    case = make_case(
        answer_contains=["Python 岗位"],
    )
    result = make_result(answer="PYTHON\u3000岗位")

    assert score_answer_facts(case, result).passed


def test_case_passes_only_when_all_metrics_pass() -> None:
    case = make_case(answer_contains=["完成"])

    score = score_case(case, make_result(answer="已完成。"))

    assert score.status == "PASS"
    assert score.passed
    assert len(score.metrics) == 6


def test_one_metric_failure_makes_case_fail() -> None:
    case = make_case(answer_contains=["必须出现"])

    score = score_case(case, make_result(answer="没有该事实。"))

    assert score.status == "FAIL"
    assert not score.passed
    assert any(metric.name == "answer_facts" for metric in score.metrics if not metric.passed)


def make_run(results: list[EvaluationCaseResult]) -> EvaluationRunResult:
    return EvaluationRunResult(
        dataset_path="synthetic.jsonl",
        results=results,
        total_cases=len(results),
        completed_cases=sum(result.status == "completed" for result in results),
        failed_cases=sum(result.status == "failed" for result in results),
    )


def test_run_metrics_aggregate_by_case_id_not_position() -> None:
    first = make_case(case_id="first", answer_contains=["完成"])
    second = make_case(case_id="second", answer_contains=["完成"])
    run = make_run(
        [
            make_result(case_id="second", answer="已完成。"),
            make_result(case_id="first", answer="已完成。"),
        ]
    )

    score = score_run([first, second], run)

    assert score.status == "PASS"
    assert score.passed_cases == 2
    assert score.case_pass_rate == 1
    assert score.metric_pass_rates["answer_facts"] == 1


def test_run_reports_missing_evaluation_result() -> None:
    expected = make_case(case_id="missing")
    score = score_run([expected], make_run([]))

    assert score.status == "FAIL"
    assert score.missing_case_ids == ["missing"]
    assert score.failed_case_ids == ["missing"]
    assert any("Missing actual result" in error for error in score.alignment_errors)


def test_run_reports_unexpected_case_id() -> None:
    expected = make_case(case_id="expected")
    score = score_run(
        [expected],
        make_run([make_result(case_id="unexpected")]),
    )

    assert score.status == "FAIL"
    assert score.unexpected_case_ids == ["unexpected"]
    assert any("Unexpected actual case_id" in error for error in score.alignment_errors)
