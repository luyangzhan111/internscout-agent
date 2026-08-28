import json
from pathlib import Path
from typing import Any
from unittest.mock import mock_open, patch

import pytest
from pydantic import ValidationError

from evals.dataset import load_eval_cases
from evals.retrieval_contracts import RetrievalEvalCase
from evals.retrieval_dataset import (
    iter_retrieval_cases,
    load_retrieval_cases,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = PROJECT_ROOT / "evals" / "cases" / "retrieval_cases.jsonl"
SCHEMA_PATH = PROJECT_ROOT / "evals" / "cases" / "retrieval_case.schema.json"

EXPECTED_CASE_IDS = [
    "retrieval_ai_rag",
    "retrieval_backend_api",
    "retrieval_automated_testing",
    "retrieval_data_crawling",
    "retrieval_devops",
    "retrieval_functional_testing",
]
EXPECTED_JOB_IDS = {
    "retrieval_ai_rag": 5,
    "retrieval_backend_api": 1,
    "retrieval_automated_testing": 2,
    "retrieval_data_crawling": 3,
    "retrieval_devops": 4,
    "retrieval_functional_testing": 6,
}


def load_raw_cases() -> list[dict[str, Any]]:
    with DATASET_PATH.open(encoding="utf-8") as dataset_file:
        return [json.loads(line) for line in dataset_file if line.strip()]


def test_default_retrieval_dataset_loads_six_cases_in_stable_order() -> None:
    cases = load_retrieval_cases()

    assert len(cases) == 6
    assert [case.case_id for case in cases] == EXPECTED_CASE_IDS
    assert len({case.case_id for case in cases}) == len(cases)


def test_retrieval_cases_have_authoritative_job_ids_and_top_k() -> None:
    cases = load_retrieval_cases()

    assert {case.case_id: case.expected_job_id for case in cases} == EXPECTED_JOB_IDS
    assert all(case.top_k == 3 for case in cases)
    assert all(case.schema_version == 1 for case in cases)
    assert all(case.description.strip() for case in cases)
    assert all(case.query.strip() for case in cases)


def test_retrieval_schema_declares_strict_contract() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert DATASET_PATH.is_file()
    assert SCHEMA_PATH.is_file()
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "schema_version",
        "case_id",
        "description",
        "query",
        "top_k",
        "expected_job_id",
    }
    assert schema["properties"]["schema_version"]["const"] == 1
    assert schema["properties"]["top_k"]["minimum"] == 1
    assert schema["properties"]["top_k"]["maximum"] == 20
    assert schema["properties"]["expected_job_id"]["minimum"] == 1


def test_retrieval_contract_rejects_blank_text_and_invalid_ids() -> None:
    base_case = load_retrieval_cases()[0].model_dump()

    for field in ("case_id", "description", "query"):
        payload = {**base_case, field: "   "}
        with pytest.raises(ValidationError):
            RetrievalEvalCase.model_validate(payload)

    for field, value in (("top_k", 0), ("top_k", 21), ("expected_job_id", 0)):
        payload = {**base_case, field: value}
        with pytest.raises(ValidationError):
            RetrievalEvalCase.model_validate(payload)


@pytest.mark.parametrize("schema_version", [True, False, 0, 2])
def test_retrieval_contract_rejects_invalid_schema_versions(
    schema_version: object,
) -> None:
    payload = {**load_retrieval_cases()[0].model_dump(), "schema_version": schema_version}

    with pytest.raises(ValidationError):
        RetrievalEvalCase.model_validate(payload)


def test_retrieval_contract_accepts_schema_version_one() -> None:
    payload = {**load_retrieval_cases()[0].model_dump(), "schema_version": 1}

    case = RetrievalEvalCase.model_validate(payload)

    assert case.schema_version == 1


def test_retrieval_contract_rejects_unknown_field() -> None:
    payload = load_retrieval_cases()[0].model_dump()
    payload["unexpected"] = True

    with pytest.raises(ValidationError):
        RetrievalEvalCase.model_validate(payload)


def test_retrieval_dataset_loader_rejects_duplicate_case_ids() -> None:
    payload = load_raw_cases()[0]
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
        with pytest.raises(ValueError, match="Duplicate retrieval evaluation case ID"):
            list(iter_retrieval_cases("duplicate.jsonl"))


def test_retrieval_dataset_loader_reports_invalid_json() -> None:
    with patch.object(Path, "open", mock_open(read_data='{"schema_version":')):
        with pytest.raises(ValueError, match="Invalid JSON.*line 1"):
            list(iter_retrieval_cases("invalid.jsonl"))


def test_retrieval_dataset_loader_reports_invalid_contract() -> None:
    payload = load_raw_cases()[0]
    del payload["query"]

    with patch.object(
        Path,
        "open",
        mock_open(read_data=json.dumps(payload) + "\n"),
    ):
        with pytest.raises(ValueError, match="Invalid retrieval evaluation case.*line 1"):
            list(iter_retrieval_cases("invalid-contract.jsonl"))


def test_stage12_dataset_still_loads_unchanged() -> None:
    cases = load_eval_cases()

    assert len(cases) == 9
    assert cases[0].case_id == "search_jobs_by_city_and_skill"
