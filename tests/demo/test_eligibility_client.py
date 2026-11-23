"""Unknown input semantics, HTTP boundaries, and evidence integrity."""

import copy
import json

import httpx
import pytest

from demo.client import BackendRequestError, BackendResponseError, BackendTimeoutError
from demo.data_client import LibraryJob
from demo.eligibility_client import (
    EligibilityApiClient,
    EligibilityResponse,
    build_eligibility_profile,
    results_match_current_jobs,
)


def job_payload():
    return {
        "id": 7, "title": "开发实习生", "company": "示例公司", "city": "深圳",
        "description": "2027届，本科及以上，经验不限，至少实习6个月。<b>原文</b>",
        "source": "manual", "source_url": "https://example.com/jobs/7",
        "status": "unknown", "updated_at": "2026-11-12T01:00:00",
    }


def response_payload(job=None):
    job = copy.deepcopy(job or job_payload())
    dimensions = ("graduation_year", "degree", "experience", "city", "internship_duration")
    return {
        "items": [{
            "job": job, "overall": "unknown", "reason": "尚有条件需要核实",
            "checks": [{
                "dimension": dimension, "status": "unknown", "reason": "候选人信息未提供",
                "candidate_value": "未填写", "requirement": "待核对",
                "evidence": [{
                    "field": "description", "text": job["description"],
                    "start": 0, "end": len(job["description"]),
                }], "notes": ["硕士优先，仅作偏好"],
            } for dimension in dimensions],
            "blocking_reasons": [], "source_fingerprint": "test", "rules_version": "test-v1",
        }], "assessed_at": "2026-11-12T01:00:00",
    }


def test_empty_profile_does_not_assume_candidate_information():
    assert build_eligibility_profile() == {
        "graduation_year": None, "degree": None, "degree_status": None,
        "work_experience_months": None, "acceptable_cities": None, "internship_months": None,
    }


def test_zero_experience_and_unrestricted_cities_are_explicit_values():
    profile = build_eligibility_profile(work_experience_months="0", city_mode="unrestricted")
    assert profile["work_experience_months"] == 0
    assert profile["acceptable_cities"] == []


def test_selected_cities_are_normalized_without_changing_degree_status():
    profile = build_eligibility_profile(
        graduation_year=" 2027 ", degree="bachelor", degree_status="enrolled",
        work_experience_months="0", city_mode="selected", cities_text="深圳，北京、深圳",
        internship_months="6",
    )
    assert profile == {
        "graduation_year": 2027, "degree": "bachelor", "degree_status": "enrolled",
        "work_experience_months": 0, "acceptable_cities": ["深圳", "北京"], "internship_months": 6,
    }


@pytest.mark.parametrize("changes", [
    {"graduation_year": "1999"}, {"graduation_year": "2027.5"},
    {"work_experience_months": "-1"}, {"internship_months": "121"},
    {"city_mode": "selected", "cities_text": "， "},
])
def test_invalid_inputs_do_not_turn_into_permissive_defaults(changes):
    with pytest.raises(ValueError):
        build_eligibility_profile(**changes)


def test_evaluate_uses_only_the_eligibility_http_endpoint():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=response_payload())

    client = EligibilityApiClient(transport=httpx.MockTransport(handler))
    profile = build_eligibility_profile()
    response = client.evaluate(profile=profile, job_ids=[7])
    assert requests[0].url.path == "/api/eligibility/evaluate"
    assert json.loads(requests[0].content) == {"profile": profile, "job_ids": [7]}
    assert response.items[0].overall == "unknown"
    assert results_match_current_jobs(response, [LibraryJob.model_validate(job_payload())])


@pytest.mark.parametrize("defect", ["quote", "span", "missing_check", "duplicate_check", "wrong_job", "duplicate_job"])
def test_untrustworthy_response_is_rejected_before_rendering(defect):
    payload = response_payload()
    item = payload["items"][0]
    if defect == "quote":
        item["checks"][0]["evidence"][0]["text"] = "未在原文出现的要求"
    elif defect == "span":
        item["checks"][0]["evidence"][0]["start"] = 1
    elif defect == "missing_check":
        item["checks"].pop()
    elif defect == "duplicate_check":
        item["checks"][0]["dimension"] = "degree"
    elif defect == "wrong_job":
        item["job"]["id"] = 8
    elif defect == "duplicate_job":
        payload["items"].append(copy.deepcopy(item))
    client = EligibilityApiClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)
    ))
    with pytest.raises(BackendResponseError):
        client.evaluate(profile=build_eligibility_profile(), job_ids=[7])


@pytest.mark.parametrize("field,value", [
    ("description", "已修改原文"), ("status", "closed"),
    ("city", "北京"), ("source_url", "https://example.com/jobs/new"),
    ("updated_at", "2026-11-12T02:00:00"),
])
def test_changed_job_cannot_reuse_old_decision(field, value):
    response = EligibilityResponse.model_validate(response_payload())
    current = job_payload()
    current[field] = value
    assert not results_match_current_jobs(response, [LibraryJob.model_validate(current)])


def test_timeout_is_reported_as_evaluation_failure_without_import_instructions():
    def handler(request):
        raise httpx.ReadTimeout("timeout", request=request)

    client = EligibilityApiClient(transport=httpx.MockTransport(handler))
    with pytest.raises(BackendTimeoutError, match="重新判断"):
        client.evaluate(profile=build_eligibility_profile(), job_ids=[7])


def test_missing_job_error_remains_visible():
    client = EligibilityApiClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(404, json={"detail": "岗位不存在，请刷新岗位。"})
    ))
    with pytest.raises(BackendRequestError, match="岗位不存在"):
        client.evaluate(profile=build_eligibility_profile(), job_ids=[7])


@pytest.mark.parametrize("category", [
    "candidate_missing", "source_unspecified", "interpretation_uncertain", "requirements_conflict",
])
def test_structured_unknown_cause_and_next_step_remain_separate_from_evidence(category):
    payload = response_payload()
    payload["items"][0]["checks"][0].update(unknown_reason=category, next_step="请核对毕业年份。")
    response = EligibilityResponse.model_validate(payload)
    check = response.items[0].checks[0]
    assert check.unknown_reason == category
    assert check.next_step == "请核对毕业年份。"
    assert check.evidence[0].text == job_payload()["description"]


def test_legacy_unknown_reason_is_not_inferred_from_old_chinese_prose():
    check = EligibilityResponse.model_validate(response_payload()).items[0].checks[0]
    assert check.reason == "候选人信息未提供"
    assert check.unknown_reason is None
    assert check.next_step == ""


@pytest.mark.parametrize("changes", [
    {"unknown_reason": "guessed"},
    {"status": "met", "unknown_reason": "candidate_missing"},
    {"status": "not_met", "next_step": "请补充信息后再判断。"},
])
def test_invalid_uncertainty_metadata_is_rejected(changes):
    payload = response_payload()
    payload["items"][0]["checks"][0].update(changes)
    client = EligibilityApiClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)
    ))
    with pytest.raises(BackendResponseError):
        client.evaluate(profile=build_eligibility_profile(), job_ids=[7])
