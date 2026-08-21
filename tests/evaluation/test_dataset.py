import json
from pathlib import Path
from typing import Any
from unittest.mock import mock_open, patch

import pytest

from evals.dataset import iter_eval_cases, load_eval_cases

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = PROJECT_ROOT / "evals" / "cases" / "agent_cases.jsonl"
SCHEMA_PATH = PROJECT_ROOT / "evals" / "cases" / "agent_case.schema.json"

TOP_LEVEL_FIELDS = {
    "schema_version",
    "case_id",
    "category",
    "description",
    "user_message",
    "expected",
}
EXPECTED_FIELDS = {
    "outcome",
    "tool_sequence",
    "tool_calls",
    "tool_results",
    "answer",
}
TOOL_CALL_FIELDS = {"tool_name", "arguments"}
TOOL_RESULT_FIELDS = {"tool_name", "success"}
DATA_ASSERTION_FIELDS = {"path", "equals", "contains"}
ANSWER_FIELDS = {"contains", "excludes"}


def load_cases() -> list[dict[str, Any]]:
    with DATASET_PATH.open(encoding="utf-8") as dataset_file:
        return [json.loads(line) for line in dataset_file if line.strip()]


def test_dataset_files_exist() -> None:
    assert DATASET_PATH.is_file()
    assert SCHEMA_PATH.is_file()


def test_schema_is_valid_json_and_declares_required_fields() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == TOP_LEVEL_FIELDS
    assert set(schema["$defs"]["expected"]["required"]) == EXPECTED_FIELDS
    assert schema["$defs"]["tool_result"]["properties"][
        "data_assertions"
    ]["type"] == "array"
    assert "data_assertion" in schema["$defs"]
    assert schema["$defs"]["data_assertion"]["oneOf"]


def test_dataset_contains_required_scenario_categories() -> None:
    cases = [case.model_dump() for case in load_eval_cases()]
    categories = {case["category"] for case in cases}

    assert {"search_jobs", "get_job_detail", "match_jobs", "failure"} <= categories
    assert len(cases) == 9


def test_each_case_has_complete_schema_fields() -> None:
    case_models = load_eval_cases()
    case_ids: set[str] = set()

    for case_model in case_models:
        case = case_model.model_dump()
        assert set(case) == TOP_LEVEL_FIELDS
        assert case["schema_version"] == 1
        assert isinstance(case["case_id"], str)
        assert case["case_id"] not in case_ids
        case_ids.add(case["case_id"])
        assert case["category"] in {
            "search_jobs",
            "get_job_detail",
            "match_jobs",
            "failure",
        }
        assert case["description"].strip()
        assert case["user_message"].strip()

        expected = case["expected"]
        assert set(expected) == EXPECTED_FIELDS
        assert expected["outcome"] in {"success", "controlled_failure"}
        assert isinstance(expected["tool_sequence"], list)
        assert isinstance(expected["tool_calls"], list)
        assert isinstance(expected["tool_results"], list)
        assert set(expected["answer"]) == ANSWER_FIELDS

        assert [call["tool_name"] for call in expected["tool_calls"]] == expected[
            "tool_sequence"
        ]
        assert [result["tool_name"] for result in expected["tool_results"]] == expected[
            "tool_sequence"
        ]

        for call in expected["tool_calls"]:
            assert set(call) == TOOL_CALL_FIELDS
            assert isinstance(call["arguments"], dict)

        for result_model, result in zip(
            case_model.expected.tool_results,
            expected["tool_results"],
        ):
            assert TOOL_RESULT_FIELDS <= set(result)
            assert isinstance(result["success"], bool)
            for assertion in result_model.data_assertions:
                assert assertion.model_fields_set <= DATA_ASSERTION_FIELDS
                assert assertion.model_fields_set in (
                    {"path", "equals"},
                    {"path", "contains"},
                )

        assert all(isinstance(value, str) and value.strip() for value in expected["answer"]["contains"])
        assert all(isinstance(value, str) and value.strip() for value in expected["answer"]["excludes"])


def test_dataset_loader_rejects_duplicate_case_ids() -> None:
    payload = load_cases()[0]
    duplicate_content = (
        json.dumps(payload, ensure_ascii=False)
        + "\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n"
    )

    with patch.object(
        Path,
        "open",
        mock_open(read_data=duplicate_content),
    ):
        with pytest.raises(ValueError, match="Duplicate evaluation case ID"):
            list(iter_eval_cases("duplicate.jsonl"))
