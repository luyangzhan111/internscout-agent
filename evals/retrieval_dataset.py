"""JSONL loader for the offline direct retrieval evaluation dataset."""

import json
from pathlib import Path
from typing import Iterator

from pydantic import ValidationError

from evals.retrieval_contracts import RetrievalEvalCase


DEFAULT_RETRIEVAL_DATASET_PATH = (
    Path(__file__).resolve().parent
    / "cases"
    / "retrieval_cases.jsonl"
)


def iter_retrieval_cases(
    path: str | Path = DEFAULT_RETRIEVAL_DATASET_PATH,
) -> Iterator[RetrievalEvalCase]:
    """Yield validated retrieval cases from a UTF-8 JSONL dataset."""

    dataset_path = Path(path)

    with dataset_path.open(encoding="utf-8") as dataset_file:
        seen_case_ids: set[str] = set()

        for line_number, raw_line in enumerate(dataset_file, start=1):
            if not raw_line.strip():
                continue

            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON in retrieval dataset {dataset_path} "
                    f"at line {line_number}."
                ) from exc

            try:
                case = RetrievalEvalCase.model_validate(payload)
            except ValidationError as exc:
                raise ValueError(
                    f"Invalid retrieval evaluation case in {dataset_path} "
                    f"at line {line_number}: {exc}"
                ) from exc

            if case.case_id in seen_case_ids:
                raise ValueError(
                    f"Duplicate retrieval evaluation case ID '{case.case_id}' "
                    f"in {dataset_path} at line {line_number}."
                )

            seen_case_ids.add(case.case_id)
            yield case


def load_retrieval_cases(
    path: str | Path = DEFAULT_RETRIEVAL_DATASET_PATH,
) -> list[RetrievalEvalCase]:
    """Load and validate all retrieval cases from a JSONL dataset."""

    return list(iter_retrieval_cases(path))
