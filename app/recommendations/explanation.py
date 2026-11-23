"""Strictly parse a single model response without adding any model request."""

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.recommendations.contracts import JobExplanation


class _ExplanationEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jobs: list[JobExplanation] = Field(max_length=50)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate fields are not accepted in an explanation.")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("Nonstandard JSON constants are not accepted.")


def parse_job_explanations(
    text: str, recommended_job_ids: list[int],
) -> list[JobExplanation]:
    """Validate exact job coverage, then restore authoritative rule order.

    Malformed output raises ValueError. Callers retain the raw response for
    compatibility while exposing no structured reasons; no repair call is made.
    """

    if not isinstance(text, str):
        raise ValueError("An explanation must be text.")
    if any(type(job_id) is not int or job_id <= 0 for job_id in recommended_job_ids):
        raise ValueError("Recommended IDs must be positive integers.")
    if len(set(recommended_job_ids)) != len(recommended_job_ids):
        raise ValueError("Recommended IDs must be unique.")
    document = text.strip()
    fenced = re.fullmatch(r"```(?:json)?[ \t]*\r?\n(?P<body>[\s\S]*?)\r?\n```", document, re.I)
    if fenced:
        document = fenced.group("body").strip()
    try:
        decoded = json.loads(document, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except RecursionError as exc:
        raise ValueError("Explanation JSON nesting is too deep.") from exc
    envelope = _ExplanationEnvelope.model_validate(decoded)
    ids = [item.job_id for item in envelope.jobs]
    if len(ids) != len(set(ids)) or set(ids) != set(recommended_job_ids):
        raise ValueError("Explanation IDs must exactly match the recommended jobs.")
    by_id = {item.job_id: item for item in envelope.jobs}
    return [by_id[job_id] for job_id in recommended_job_ids]
