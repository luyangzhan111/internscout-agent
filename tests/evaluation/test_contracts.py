import pytest
from pydantic import ValidationError

from evals.contracts import EvalCase, EvalDataAssertion, EvalToolResult
from evals.dataset import load_eval_cases


def test_dataset_cases_validate_as_eval_case_contracts() -> None:
    cases = load_eval_cases()

    assert cases
    assert all(isinstance(case, EvalCase) for case in cases)
    assert cases[0].schema_version == 1


def test_eval_case_rejects_missing_required_field() -> None:
    payload = load_eval_cases()[0].model_dump()
    del payload["user_message"]

    with pytest.raises(ValidationError):
        EvalCase.model_validate(payload)


def test_eval_case_rejects_unknown_top_level_field() -> None:
    payload = load_eval_cases()[0].model_dump()
    payload["unexpected"] = True

    with pytest.raises(ValidationError):
        EvalCase.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"path": "field"},
        {"path": "field", "equals": 1, "contains": 1},
        {"path": "items[1]", "equals": 1},
        {"path": "items[0].field[0]", "equals": 1},
    ],
)
def test_data_assertion_rejects_invalid_contract(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EvalDataAssertion.model_validate(payload)


def test_data_assertion_supports_explicit_null_root_equality() -> None:
    assertion = EvalDataAssertion.model_validate(
        {"path": "$", "equals": None}
    )

    assert assertion.path == "$"
    assert assertion.equals is None


@pytest.mark.parametrize(
    "path",
    ["field", "field.child", "items[0]", "items[0].field"],
)
def test_data_assertion_accepts_supported_paths(path: str) -> None:
    assertion = EvalDataAssertion.model_validate(
        {"path": path, "equals": "expected"}
    )

    assert assertion.path == path


def test_tool_result_rejects_legacy_mapping_data_assertions() -> None:
    with pytest.raises(ValidationError):
        EvalToolResult.model_validate(
            {
                "tool_name": "get_job_detail",
                "success": True,
                "data_assertions": {"id": 1},
            }
        )
