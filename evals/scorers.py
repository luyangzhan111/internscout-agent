"""Deterministic, provider-neutral scoring for offline Agent evaluations."""

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from typing import Any

from app.agent.contracts import ToolExecution

from evals.contracts import (
    CaseScore,
    EvalCase,
    EvalDataAssertion,
    EvaluationCaseResult,
    EvaluationRunResult,
    EvaluationScore,
    MetricResult,
)


EXECUTION_OUTCOME = "execution_outcome"
TOOL_SELECTION = "tool_selection"
TOOL_SEQUENCE = "tool_sequence"
TOOL_ARGUMENTS = "tool_arguments"
TOOL_RESULTS = "tool_results"
ANSWER_FACTS = "answer_facts"
CORE_METRICS = (
    EXECUTION_OUTCOME,
    TOOL_SELECTION,
    TOOL_SEQUENCE,
    TOOL_ARGUMENTS,
    TOOL_RESULTS,
    ANSWER_FACTS,
)

_FIELD_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MISSING = object()


def _metric(
    name: str,
    passed: bool,
    expected: Any,
    actual: Any,
    reason: str,
) -> MetricResult:
    return MetricResult(
        name=name,
        passed=passed,
        expected=expected,
        actual=actual,
        reason=reason,
    )


def _tool_names(executions: list[ToolExecution]) -> list[str]:
    return [execution.call.tool_name for execution in executions]


def _actual_executions(result: EvaluationCaseResult) -> list[ToolExecution]:
    if result.status != "completed" or result.agent_result is None:
        return []
    return result.agent_result.tool_executions


def score_execution_outcome(
    case: EvalCase,
    result: EvaluationCaseResult,
) -> MetricResult:
    """Score Agent completion and the expected controlled failure state."""

    completed = result.status == "completed" and result.agent_result is not None
    actual_executions = _actual_executions(result)

    if case.expected.outcome == "success":
        passed = completed
        actual = "completed" if completed else result.status
        reason = (
            "Agent run completed successfully."
            if passed
            else "Agent run did not complete successfully."
        )
    else:
        expected_failure_positions = {
            index
            for index, expected_result in enumerate(
                case.expected.tool_results
            )
            if not expected_result.success
        }
        observed_expected_failure = any(
            index < len(actual_executions)
            and not actual_executions[index].result.success
            and index in expected_failure_positions
            and actual_executions[index].result.tool_name
            == case.expected.tool_results[index].tool_name
            for index in expected_failure_positions
        )
        passed = completed and observed_expected_failure
        actual = {
            "completed": completed,
            "observed_expected_tool_failure": observed_expected_failure,
        }
        reason = (
            "Agent completed with the expected failed ToolResult."
            if passed
            else "Expected controlled failure was not observed in a completed Agent run."
        )

    return _metric(
        EXECUTION_OUTCOME,
        passed,
        case.expected.outcome,
        actual,
        reason,
    )


def score_tool_selection(
    case: EvalCase,
    result: EvaluationCaseResult,
) -> MetricResult:
    """Compare selected Tool name counts, independently of sequence order."""

    expected = list(case.expected.tool_sequence)
    actual = _tool_names(_actual_executions(result))
    expected_counts = Counter(expected)
    actual_counts = Counter(actual)
    passed = expected_counts == actual_counts

    missing = list((expected_counts - actual_counts).elements())
    unexpected = list((actual_counts - expected_counts).elements())
    reason = (
        "Tool selection matches expected names and counts."
        if passed
        else f"Missing tools: {missing}; unexpected tools: {unexpected}."
    )
    return _metric(TOOL_SELECTION, passed, expected, actual, reason)


def score_tool_sequence(
    case: EvalCase,
    result: EvaluationCaseResult,
) -> MetricResult:
    """Require exact Tool count, names, and order."""

    expected = list(case.expected.tool_sequence)
    actual = _tool_names(_actual_executions(result))
    passed = expected == actual
    reason = (
        "Tool sequence matches exactly."
        if passed
        else "Tool count, names, or order differs from the expected sequence."
    )
    return _metric(TOOL_SEQUENCE, passed, expected, actual, reason)


def _compare_values(
    expected: Any,
    actual: Any,
    path: str,
) -> list[str]:
    """Return strict, recursive comparison errors for JSON-like values."""

    if type(expected) is not type(actual):
        return [
            f"{path}: expected type {type(expected).__name__}, "
            f"got {type(actual).__name__}."
        ]

    if isinstance(expected, dict):
        expected_keys = set(expected)
        actual_keys = set(actual)
        errors: list[str] = []

        for key in sorted(expected_keys - actual_keys, key=repr):
            errors.append(f"{path}: missing key {key!r}.")
        for key in sorted(actual_keys - expected_keys, key=repr):
            errors.append(f"{path}: unexpected key {key!r}.")
        for key in sorted(expected_keys & actual_keys, key=repr):
            errors.extend(
                _compare_values(
                    expected[key],
                    actual[key],
                    f"{path}.{key}",
                )
            )
        return errors

    if isinstance(expected, list):
        errors = []
        if len(expected) != len(actual):
            errors.append(
                f"{path}: expected list length {len(expected)}, "
                f"got {len(actual)}."
            )
        for index, (expected_item, actual_item) in enumerate(
            zip(expected, actual)
        ):
            errors.extend(
                _compare_values(
                    expected_item,
                    actual_item,
                    f"{path}[{index}]",
                )
            )
        return errors

    if expected != actual:
        return [f"{path}: expected {expected!r}, got {actual!r}."]
    return []


def score_tool_arguments(
    case: EvalCase,
    result: EvaluationCaseResult,
) -> MetricResult:
    """Compare raw ToolCall arguments with strict recursive semantics."""

    expected = [
        {"tool_name": call.tool_name, "arguments": call.arguments}
        for call in case.expected.tool_calls
    ]
    actual_executions = _actual_executions(result)
    actual = [
        {
            "tool_name": execution.call.tool_name,
            "arguments": execution.call.arguments,
        }
        for execution in actual_executions
    ]
    errors: list[str] = []
    if len(expected) != len(actual):
        errors.append(
            f"Expected {len(expected)} Tool calls, got {len(actual)}."
        )

    for index, (expected_call, actual_call) in enumerate(
        zip(expected, actual)
    ):
        errors.extend(
            _compare_values(
                expected_call,
                actual_call,
                f"tool_calls[{index}]",
            )
        )

    passed = not errors
    reason = "Raw ToolCall arguments match exactly." if passed else "; ".join(errors)
    return _metric(TOOL_ARGUMENTS, passed, expected, actual, reason)


def _resolve_path(data: Any, path: str) -> tuple[bool, Any, str | None]:
    """Resolve the intentionally small path language from EvalDataAssertion."""

    if path == "$":
        return True, data, None

    current = data
    for component in path.split("."):
        if component == "items[0]":
            if isinstance(current, dict):
                if "items" not in current:
                    return False, _MISSING, "field 'items' is missing"
                current = current["items"]
            if not isinstance(current, list):
                return False, _MISSING, "value at 'items' is not a list"
            if not current:
                return False, _MISSING, "list index 0 is out of range"
            current = current[0]
            continue

        if not _FIELD_PATTERN.fullmatch(component):
            return False, _MISSING, f"unsupported path component {component!r}"
        if not isinstance(current, dict):
            return False, _MISSING, f"value is not an object before {component!r}"
        if component not in current:
            return False, _MISSING, f"field {component!r} is missing"
        current = current[component]

    return True, current, None


def _contains_value(expected: Any, actual: Any) -> tuple[bool, str]:
    """Apply explicit string or list containment semantics."""

    if isinstance(expected, str) and isinstance(actual, str):
        return expected in actual, "string substring containment"

    if isinstance(actual, list):
        if isinstance(expected, list):
            remaining = list(actual)
            for expected_item in expected:
                for index, actual_item in enumerate(remaining):
                    if not _compare_values(
                        expected_item,
                        actual_item,
                        "contains",
                    ):
                        remaining.pop(index)
                        break
                else:
                    return False, "expected list is not contained in actual list"
            return True, "all expected list items are contained"

        return any(
            not _compare_values(expected, actual_item, "contains")
            for actual_item in actual
        ), "expected item containment in actual list"

    return False, "contains requires string/string or list containment"


def _assert_data(
    data: Any,
    assertion: EvalDataAssertion,
) -> str | None:
    found, actual, error = _resolve_path(data, assertion.path)
    if not found:
        return f"path {assertion.path!r} does not resolve: {error}."

    if "equals" in assertion.model_fields_set:
        errors = _compare_values(
            assertion.equals,
            actual,
            assertion.path,
        )
        return "; ".join(errors) if errors else None

    passed, containment_reason = _contains_value(
        assertion.contains,
        actual,
    )
    return None if passed else (
        f"path {assertion.path!r} failed {containment_reason}: "
        f"expected {assertion.contains!r}, got {actual!r}."
    )


def score_tool_results(
    case: EvalCase,
    result: EvaluationCaseResult,
) -> MetricResult:
    """Compare ToolResult metadata and generic path-based data assertions."""

    expected = [
        {
            "tool_name": tool_result.tool_name,
            "success": tool_result.success,
            "error_contains": tool_result.error_contains,
            "data_assertions": [
                assertion.model_dump(exclude_unset=True)
                for assertion in tool_result.data_assertions
            ],
        }
        for tool_result in case.expected.tool_results
    ]
    actual_executions = _actual_executions(result)
    actual = [
        {
            "tool_name": execution.result.tool_name,
            "success": execution.result.success,
            "error": execution.result.error,
            "data": execution.result.data,
        }
        for execution in actual_executions
    ]
    errors: list[str] = []
    if len(expected) != len(actual):
        errors.append(
            f"Expected {len(expected)} Tool results, got {len(actual)}."
        )

    for index, (expected_result, actual_execution) in enumerate(
        zip(case.expected.tool_results, actual_executions)
    ):
        actual_result = actual_execution.result
        if expected_result.tool_name != actual_result.tool_name:
            errors.append(
                f"tool_results[{index}].tool_name: expected "
                f"{expected_result.tool_name!r}, got {actual_result.tool_name!r}."
            )
        if expected_result.success != actual_result.success:
            errors.append(
                f"tool_results[{index}].success: expected "
                f"{expected_result.success!r}, got {actual_result.success!r}."
            )

        for expected_error in expected_result.error_contains:
            if actual_result.error is None:
                errors.append(
                    f"tool_results[{index}].error is missing; expected "
                    f"substring {expected_error!r}."
                )
            elif expected_error not in actual_result.error:
                errors.append(
                    f"tool_results[{index}].error does not contain "
                    f"{expected_error!r}."
                )

        for assertion in expected_result.data_assertions:
            assertion_error = _assert_data(
                actual_result.data,
                assertion,
            )
            if assertion_error is not None:
                errors.append(f"tool_results[{index}]: {assertion_error}")

    passed = not errors
    reason = "Tool results match all expected observations." if passed else "; ".join(errors)
    return _metric(TOOL_RESULTS, passed, expected, actual, reason)


def normalize_answer_text(value: str) -> str:
    """Normalize answer text without changing its fact-level meaning."""

    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.split()).casefold()


def score_answer_facts(
    case: EvalCase,
    result: EvaluationCaseResult,
) -> MetricResult:
    """Check required and forbidden normalized answer substrings."""

    expected_contains = [
        normalize_answer_text(value)
        for value in case.expected.answer.contains
    ]
    expected_excludes = [
        normalize_answer_text(value)
        for value in case.expected.answer.excludes
    ]
    answer = (
        result.agent_result.answer
        if result.status == "completed" and result.agent_result is not None
        else None
    )
    actual = normalize_answer_text(answer) if answer is not None else None
    missing = [
        value for value in expected_contains
        if actual is None or value not in actual
    ]
    forbidden = [
        value for value in expected_excludes
        if actual is not None and value in actual
    ]
    passed = actual is not None and not missing and not forbidden
    reason = (
        "Answer contains all required facts and no excluded facts."
        if passed
        else f"Missing required facts: {missing}; forbidden facts present: {forbidden}."
    )
    return _metric(
        ANSWER_FACTS,
        passed,
        {
            "contains": expected_contains,
            "excludes": expected_excludes,
        },
        actual,
        reason,
    )


def score_case(
    case: EvalCase,
    result: EvaluationCaseResult,
) -> CaseScore:
    """Score one case using AND semantics across all core metrics."""

    metrics = [
        score_execution_outcome(case, result),
        score_tool_selection(case, result),
        score_tool_sequence(case, result),
        score_tool_arguments(case, result),
        score_tool_results(case, result),
        score_answer_facts(case, result),
    ]
    failure_reasons = [
        f"{metric.name}: {metric.reason}"
        for metric in metrics
        if not metric.passed
    ]
    passed = not failure_reasons
    return CaseScore(
        case_id=case.case_id,
        status="PASS" if passed else "FAIL",
        metrics=metrics,
        failure_reasons=failure_reasons,
    )


def score_run(
    cases: Iterable[EvalCase],
    run: EvaluationRunResult,
) -> EvaluationScore:
    """Score cases by case ID and report missing or unexpected observations."""

    expected_cases = list(cases)
    expected_by_id: dict[str, EvalCase] = {}
    alignment_errors: list[str] = []
    for case in expected_cases:
        if case.case_id in expected_by_id:
            alignment_errors.append(
                f"Duplicate expected case_id {case.case_id!r}."
            )
        expected_by_id.setdefault(case.case_id, case)

    actual_by_id: dict[str, EvaluationCaseResult] = {}
    for result in run.results:
        if result.case_id in actual_by_id:
            alignment_errors.append(
                f"Duplicate actual case_id {result.case_id!r}."
            )
        actual_by_id.setdefault(result.case_id, result)

    missing_case_ids = [
        case.case_id
        for case in expected_cases
        if case.case_id not in actual_by_id
    ]
    unexpected_case_ids = sorted(
        set(actual_by_id) - set(expected_by_id)
    )
    alignment_errors.extend(
        f"Missing actual result for case_id {case_id!r}."
        for case_id in missing_case_ids
    )
    alignment_errors.extend(
        f"Unexpected actual case_id {case_id!r}."
        for case_id in unexpected_case_ids
    )

    case_scores: list[CaseScore] = []
    for case in expected_cases:
        actual_result = actual_by_id.get(case.case_id)
        if actual_result is None:
            actual_result = EvaluationCaseResult(
                case_id=case.case_id,
                status="failed",
                error_type="MissingEvaluationResult",
                error_message="No actual result was supplied for this case.",
            )
        case_scores.append(score_case(case, actual_result))

    total_cases = len(case_scores)
    passed_cases = sum(case_score.passed for case_score in case_scores)
    failed_cases = total_cases - passed_cases
    metric_pass_rates: dict[str, float] = {}
    for metric_name in CORE_METRICS:
        passed_metrics = sum(
            metric.passed
            for case_score in case_scores
            for metric in case_score.metrics
            if metric.name == metric_name
        )
        metric_pass_rates[metric_name] = (
            passed_metrics / total_cases if total_cases else 0.0
        )

    failed_case_ids = [
        case_score.case_id
        for case_score in case_scores
        if not case_score.passed
    ]
    fully_passed = (
        total_cases > 0
        and not failed_case_ids
        and not alignment_errors
    )
    return EvaluationScore(
        total_cases=total_cases,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        case_pass_rate=passed_cases / total_cases if total_cases else 0.0,
        metric_pass_rates=metric_pass_rates,
        failed_case_ids=failed_case_ids,
        case_scores=case_scores,
        missing_case_ids=missing_case_ids,
        unexpected_case_ids=unexpected_case_ids,
        alignment_errors=alignment_errors,
        status="PASS" if fully_passed else "FAIL",
    )
