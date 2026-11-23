"""Structured candidate semantics and trustworthy recommendation responses."""

import copy
import json

import httpx
import pytest

from demo.client import BackendResponseError, BackendTimeoutError
from demo.recommendation_client import AgentRecommendationResponse, RecommendationApiClient, build_recommendation_candidate
from demo.recommendation_scope import is_sample_record


def eligibility(job_id=1, overall="unknown", *, closed=False):
    job = {
        "id": job_id, "title": f"岗位{job_id}", "company": "示例公司", "city": "深圳",
        "description": "本科及以上；<b>岗位原文</b>", "source": "manual",
        "source_url": f"https://example.com/jobs/{job_id}", "status": "closed" if closed else "unknown",
        "updated_at": "2026-11-12T01:00:00",
    }
    return {
        "job": job, "overall": overall, "reason": "条件仍需核对" if overall == "unknown" else "规则判断结果",
        "checks": [{
            "dimension": dimension, "status": overall, "reason": "测试条件理由",
            "candidate_value": "未填写", "requirement": "本科及以上",
            "evidence": [{"field": "description", "text": "本科及以上", "start": 0, "end": 5}],
            "notes": ["硕士优先，只作为偏好"],
        } for dimension in ("graduation_year", "degree", "experience", "city", "internship_duration")],
        "blocking_reasons": ["明确条件不满足"] if overall == "not_met" else [],
        "source_fingerprint": "test", "rules_version": "test-v1",
    }


def recommendation(job_id=1, overall="unknown", score=50):
    result = eligibility(job_id, overall)
    return {
        "job": copy.deepcopy(result["job"]), "match_score": score,
        "matched_skills": ["Python"], "missing_skills": ["SQL"],
        "detected_job_skills": ["Python", "SQL"], "reason": "partial_match", "eligibility": result,
    }


def response_payload():
    return {
        "recommendations": [recommendation()], "excluded": [],
        "counts": {"evaluated": 1, "met": 0, "unknown": 1, "not_met": 0, "closed": 0, "returned": 1},
        "limit": 10, "assessed_at": "2026-11-12T01:00:00", "summary": "推荐 1 个待确认岗位。",
        "model_explanation": None, "explanation_status": "unavailable",
        "explanation_notice": "尚未配置模型，规则结果仍可使用。", "steps": 0, "tool_execution_count": 0,
    }


def test_skills_are_required_but_conditions_are_not_assumed():
    candidate = build_recommendation_candidate(skills_text="Python，SQL、Python")
    assert candidate["skills"] == ["Python", "SQL"]
    assert all(value is None for value in candidate["conditions"].values())
    with pytest.raises(ValueError, match="至少填写一项"):
        build_recommendation_candidate(skills_text="， ")


def test_city_unknown_unrestricted_and_zero_experience_remain_distinct():
    unknown = build_recommendation_candidate(skills_text="Python")
    explicit = build_recommendation_candidate(
        skills_text="Python", city_mode="unrestricted", work_experience_months="0"
    )
    assert unknown["conditions"]["acceptable_cities"] is None
    assert unknown["conditions"]["work_experience_months"] is None
    assert explicit["conditions"]["acceptable_cities"] == []
    assert explicit["conditions"]["work_experience_months"] == 0


def test_structured_candidate_is_sent_to_new_endpoint_without_model_arguments():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=response_payload())

    client = RecommendationApiClient(transport=httpx.MockTransport(handler))
    candidate = build_recommendation_candidate(skills_text="Python")
    result = client.recommend(candidate=candidate, explain_with_model=False)
    assert result.recommendations[0].eligibility.overall == "unknown"
    assert requests[0].url.path == "/api/agent/recommend"
    assert json.loads(requests[0].content) == {
        "candidate": {"skills": candidate["skills"], "conditions": candidate["conditions"]},
        "limit": 10, "explain_with_model": False, "include_samples": False,
    }
    assert candidate["target_directions"] == []


@pytest.mark.parametrize("defect", [
    "quote", "snapshot", "counts", "returned", "missing_checks", "skill_partition",
    "blocked_recommendation", "closed_recommendation", "reordered", "overlap", "limit",
])
def test_incomplete_or_inconsistent_results_are_not_accepted(defect):
    payload = response_payload()
    item = payload["recommendations"][0]
    if defect == "quote":
        item["eligibility"]["checks"][0]["evidence"][0]["text"] = "硕士及以上"
    elif defect == "snapshot":
        item["eligibility"]["job"]["description"] += "补充要求"
    elif defect == "counts":
        payload["counts"]["evaluated"] = 9
    elif defect == "returned":
        payload["counts"]["returned"] = 0
    elif defect == "missing_checks":
        item["eligibility"]["checks"].pop()
    elif defect == "skill_partition":
        item["missing_skills"] = ["Python"]
    elif defect == "blocked_recommendation":
        item["eligibility"]["overall"] = "not_met"
    elif defect == "closed_recommendation":
        item["job"]["status"] = item["eligibility"]["job"]["status"] = "closed"
    elif defect == "reordered":
        payload["recommendations"] = [recommendation(1, "unknown"), recommendation(2, "met")]
        payload["counts"].update(evaluated=2, met=1, returned=2)
    elif defect == "overlap":
        payload["excluded"] = [eligibility(1, "not_met")]
        payload["counts"].update(evaluated=2, not_met=1)
    elif defect == "limit":
        payload["limit"] = 1
    client = RecommendationApiClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)
    ))
    with pytest.raises(BackendResponseError):
        client.recommend(candidate=build_recommendation_candidate(skills_text="Python"))


def test_unknown_group_order_is_preserved_without_model_reordering():
    payload = response_payload()
    payload["recommendations"] = [recommendation(1, "met", 10), recommendation(2, "unknown", 100)]
    payload["counts"].update(evaluated=2, met=1, returned=2)
    payload.update(explanation_status="generated", model_explanation="先关注岗位2。")
    client = RecommendationApiClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)
    ))
    result = client.recommend(candidate=build_recommendation_candidate(skills_text="Python"))
    assert [item.job.id for item in result.recommendations] == [1, 2]


def test_invalid_json_is_rejected():
    client = RecommendationApiClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, text="not JSON")
    ))
    with pytest.raises(BackendResponseError):
        client.recommend(candidate=build_recommendation_candidate(skills_text="Python"))


def test_timeout_never_retries_a_model_enabled_request():
    requests = []

    def handler(request):
        requests.append(request)
        raise httpx.ReadTimeout("timed out", request=request)

    client = RecommendationApiClient(transport=httpx.MockTransport(handler))
    with pytest.raises(BackendTimeoutError, match="不会自动重试"):
        client.recommend(candidate=build_recommendation_candidate(skills_text="Python"))
    assert len(requests) == 1


def generated_payload():
    payload = response_payload()
    payload["recommendations"].append(recommendation(2))
    payload["counts"].update(evaluated=2, unknown=2, returned=2)
    payload.update(explanation_status="generated", model_explanation="旧文本仍作为兼容来源。")
    payload["job_explanations"] = [
        {"job_id": 1, "reasons": ["Python技能有交集。"]},
        {"job_id": 2, "reasons": ["岗位涉及Python服务开发。"]},
    ]
    return payload


def test_valid_structured_reasons_cover_exact_recommendation_order_without_old_text():
    payload = generated_payload()
    payload["model_explanation"] = None
    result = AgentRecommendationResponse.model_validate(payload)
    assert [item.job_id for item in result.job_explanations] == [1, 2]
    assert result.job_explanations[0].reasons == ["Python技能有交集。"]


@pytest.mark.parametrize("defect", [
    "missing_job", "unknown_job", "duplicate_job", "reordered", "bool_id", "string_id",
    "empty_reason", "numeric_reason", "no_reasons", "too_many_reasons", "invalid_shape", "null",
])
@pytest.mark.parametrize("legacy_text", ["旧文本仍作为兼容来源。", None])
def test_optional_malformed_job_reasons_are_dropped_without_losing_rule_cards(defect, legacy_text):
    payload = generated_payload()
    payload["model_explanation"] = legacy_text
    if defect == "missing_job":
        payload["job_explanations"].pop()
    elif defect == "unknown_job":
        payload["job_explanations"][1]["job_id"] = 999
    elif defect == "duplicate_job":
        payload["job_explanations"][1]["job_id"] = 1
    elif defect == "reordered":
        payload["job_explanations"].reverse()
    elif defect == "bool_id":
        payload["job_explanations"][0]["job_id"] = True
    elif defect == "string_id":
        payload["job_explanations"][0]["job_id"] = "1"
    elif defect == "empty_reason":
        payload["job_explanations"][0]["reasons"] = [" "]
    elif defect == "numeric_reason":
        payload["job_explanations"][0]["reasons"] = [100]
    elif defect == "no_reasons":
        payload["job_explanations"][0]["reasons"] = []
    elif defect == "too_many_reasons":
        payload["job_explanations"][0]["reasons"] *= 4
    elif defect == "invalid_shape":
        payload["job_explanations"] = {"job_id": 1}
    else:
        payload["job_explanations"] = None
    client = RecommendationApiClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)
    ))
    result = client.recommend(candidate=build_recommendation_candidate(skills_text="Python"))
    assert [item.job.id for item in result.recommendations] == [1, 2]
    assert result.job_explanations == []
    if legacy_text is None:
        assert result.explanation_status == "failed"
        assert "格式不完整" in result.explanation_notice


def test_empty_generated_explanation_preserves_rule_response_with_visible_fallback():
    payload = response_payload()
    payload["explanation_status"] = "generated"
    result = AgentRecommendationResponse.model_validate(payload)
    assert len(result.recommendations) == 1
    assert result.explanation_status == "failed"
    assert "规则推荐结果仍可查看" in result.explanation_notice


@pytest.mark.parametrize("status", ["disabled", "unavailable", "failed", "stale", "not_needed"])
def test_structured_reasons_are_dropped_outside_generated_status(status):
    payload = generated_payload()
    payload.update(explanation_status=status, model_explanation=None)
    result = AgentRecommendationResponse.model_validate(payload)
    assert len(result.recommendations) == 2
    assert result.job_explanations == []


def test_generated_empty_structured_list_is_compatible_with_existing_text():
    payload = generated_payload()
    payload["job_explanations"] = []
    assert AgentRecommendationResponse.model_validate(payload).job_explanations == []
    del payload["job_explanations"]
    assert AgentRecommendationResponse.model_validate(payload).job_explanations == []


def scoped_payload():
    payload = response_payload()
    job = payload["recommendations"][0]["job"]
    job.update(source="oppo", source_url="https://careers.oppo.com/jobs/1")
    payload["recommendations"][0]["eligibility"]["job"] = copy.deepcopy(job)
    primary = {key: job.get(key) for key in (
        "source", "source_url", "status", "last_checked_at", "updated_at", "title", "company"
    )}
    primary["job_id"] = job["id"]
    payload["data_scope"] = {
        "total_records": 4, "sample_records_excluded": 2,
        "duplicate_records_collapsed": 1, "include_samples": False,
    }
    payload["duplicate_groups"] = [{
        "primary_job_id": 1, "sources": [primary, dict(primary, job_id=17, source="manual", status="closed")],
        "has_conflict": True, "selection_reason": "优先使用已接入的官网来源。",
    }]
    return payload


def test_scope_and_duplicate_sources_preserve_selected_job_and_rule_order():
    payload = scoped_payload()
    result = AgentRecommendationResponse.model_validate(payload)
    assert result.data_scope.total_records == 4
    assert result.data_scope.sample_records_excluded == 2
    assert result.data_scope.duplicate_records_collapsed == 1
    assert [item.job.id for item in result.recommendations] == [1]
    assert result.duplicate_groups[0].sources[1].status == "closed"
    assert result.recommendations[0].job.status == "unknown"


@pytest.mark.parametrize("defect", [
    "total", "negative", "bool_count", "include_excluded", "missing_primary", "unknown_primary",
    "duplicate_source", "group_overlap", "single_source", "wrong_primary_metadata", "blank_selection",
    "group_without_scope", "count_without_group", "sample_primary", "sample_secondary",
    "include_string", "second_displayed_member", "wrong_group_shape",
    "different_url", "different_title", "different_company", "different_fragment", "undisclosed_conflict",
])
def test_invalid_scope_or_source_provenance_is_rejected(defect):
    payload = scoped_payload()
    scope = payload["data_scope"]
    group = payload["duplicate_groups"][0]
    if defect == "total":
        scope["total_records"] += 1
    elif defect == "negative":
        scope["sample_records_excluded"] = -1
    elif defect == "bool_count":
        scope["duplicate_records_collapsed"] = True
    elif defect == "include_excluded":
        scope["include_samples"] = True
    elif defect == "missing_primary":
        group["sources"][0]["job_id"] = 2
    elif defect == "unknown_primary":
        group["primary_job_id"] = 17
    elif defect == "duplicate_source":
        group["sources"][1]["job_id"] = 1
    elif defect == "group_overlap":
        payload["duplicate_groups"].append(copy.deepcopy(group))
    elif defect == "single_source":
        group["sources"].pop()
    elif defect == "wrong_primary_metadata":
        group["sources"][0]["status"] = "closed"
    elif defect == "blank_selection":
        group["selection_reason"] = "  "
    elif defect == "group_without_scope":
        del payload["data_scope"]
    elif defect == "count_without_group":
        payload["duplicate_groups"] = []
    elif defect == "sample_primary":
        for job in (payload["recommendations"][0]["job"], payload["recommendations"][0]["eligibility"]["job"]):
            job["source"] = "mock"
        group["sources"][0]["source"] = "mock"
    elif defect == "sample_secondary":
        group["sources"][1]["source_url"] = "https://demo.example.org/jobs/1"
    elif defect == "include_string":
        scope["include_samples"] = "false"
    elif defect == "second_displayed_member":
        payload["excluded"] = [eligibility(17, "not_met", closed=True)]
        payload["excluded"][0]["job"]["source_url"] = "https://careers.oppo.com/jobs/1"
        payload["counts"].update(evaluated=2, closed=1)
        scope["total_records"] += 1
    elif defect == "wrong_group_shape":
        payload["duplicate_groups"] = None
    elif defect == "different_url":
        group["sources"][1]["source_url"] += "?job_id=2"
    elif defect == "different_fragment":
        group["sources"][1]["source_url"] += "#/jobs/2"
    elif defect == "different_title":
        group["sources"][1]["title"] = "另一种岗位"
    elif defect == "different_company":
        group["sources"][1]["company"] = "另一家公司"
    elif defect == "undisclosed_conflict":
        group["has_conflict"] = False
    client = RecommendationApiClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)
    ))
    with pytest.raises(BackendResponseError):
        client.recommend(candidate=build_recommendation_candidate(skills_text="Python"))


@pytest.mark.parametrize("include_samples", [False, True])
def test_requested_sample_scope_is_sent_and_must_match_response(include_samples):
    payload = scoped_payload()
    payload["data_scope"].update(total_records=2, sample_records_excluded=0, include_samples=include_samples)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=payload)

    client = RecommendationApiClient(transport=httpx.MockTransport(handler))
    candidate = build_recommendation_candidate(skills_text="Python")
    result = client.recommend(candidate=candidate, include_samples=include_samples)
    assert json.loads(requests[-1].content)["include_samples"] is include_samples
    assert result.data_scope.include_samples is include_samples
    with pytest.raises(BackendResponseError):
        client.recommend(candidate=candidate, include_samples=not include_samples)


def test_partial_display_need_not_include_unshown_duplicate_groups():
    payload = scoped_payload()
    payload["limit"] = 1
    payload["counts"].update(evaluated=2, unknown=2)
    payload["data_scope"].update(total_records=6, duplicate_records_collapsed=2)
    assert len(AgentRecommendationResponse.model_validate(payload).duplicate_groups) == 1


def test_old_server_scope_is_absent_without_assuming_isolation():
    result = AgentRecommendationResponse.model_validate(response_payload())
    assert result.data_scope is None
    assert result.duplicate_groups == []


def test_equivalent_url_origin_and_name_whitespace_are_valid_source_identity():
    payload = scoped_payload()
    source = payload["duplicate_groups"][0]["sources"][1]
    source.update(source_url=" HTTPS://CAREERS.OPPO.COM.:443/jobs/1 ", title=" 岗位1 ", company=" 示例公司 ")
    assert AgentRecommendationResponse.model_validate(payload).duplicate_groups[0].primary_job_id == 1


@pytest.mark.parametrize("source,url,expected", [
    (" Mock ", "https://real.test/jobs/1", True),
    ("manual", " https://recruit.EXAMPLE.COM./jobs/1 ", True),
    ("manual", "https://example.org/jobs/1", True),
    ("manual", "https://example.net/jobs/1", True),
    ("manual", "https://notexample.com/jobs/1", False),
    ("manual", "https://example.com.attacker.test/jobs/1", False),
])
def test_sample_labels_use_the_same_domain_boundary_as_scope(source, url, expected):
    assert is_sample_record(source, url) is expected


def _quality_item(job_id, *, direction="aligned", core="Python", overall="unknown"):
    item = recommendation(job_id, overall)
    title = {"aligned": "后端开发", "uncertain": "工程师", "unrelated": "公关营销", "not_requested": "不限方向"}[direction]
    description = f"本科及以上；掌握{core}；有{('SQL' if core == 'Python' else 'Python')}经验者优先"
    item["job"].update(title=title, description=description, source_url=f"https://careers.test/jobs/{job_id}")
    item["eligibility"]["job"] = copy.deepcopy(item["job"])
    item["direction_fit"] = {
        "status": direction, "detected_directions": {"aligned": ["backend"], "unrelated": ["other"]}.get(direction, []),
        "reason": "岗位名称明确。" if direction != "uncertain" else "岗位名称未说明方向。",
        "evidence": [] if direction == "not_requested" else [
            {"field": "title", "text": title, "start": 0, "end": len(title)},
        ],
    }
    rows = []
    for skill in item["detected_job_skills"]:
        quote = f"掌握{skill}" if skill == core else f"有{skill}经验者优先"
        start = description.index(quote)
        rows.append({"skill": skill, "matched": skill == "Python", "importance": "core" if skill == core else "bonus",
                     "evidence": [{"field": "description", "text": quote, "start": start, "end": start + len(quote)}]})
    item["skill_requirements"] = rows
    return item


def _quality_payload():
    payload = response_payload()
    payload.update(ranking_version="direction-core-v1", target_directions=["backend", "devops"],
                   recommendations=[_quality_item(2, core="Python"), _quality_item(1, core="SQL")],
                   direction_excluded=[_quality_item(3, direction="unrelated", overall="met")])
    payload["counts"].update(evaluated=3, unknown=2, direction_mismatch=1, returned=2)
    return payload


@pytest.mark.parametrize("ranking_version", ["direction-core-v1", "direction-core-v2"])
def test_requested_directions_are_stable_and_core_coverage_can_outweigh_id(ranking_version):
    requests = []
    payload = _quality_payload()
    payload["ranking_version"] = ranking_version

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=payload)

    candidate = build_recommendation_candidate(skills_text="Python", target_directions=["backend", "devops", "backend"])
    client = RecommendationApiClient(transport=httpx.MockTransport(handler))
    result = client.recommend(candidate=candidate)
    assert json.loads(requests[0].content)["candidate"]["target_directions"] == ["backend", "devops"]
    assert [item.job.id for item in result.recommendations] == [2, 1]
    assert result.direction_excluded[0].eligibility.overall == "met"
    assert result.counts.not_met == 0


@pytest.mark.parametrize("bad_targets", ["backend", [None], ["unknown"], {"backend"}, None])
def test_invalid_target_selection_does_not_expand_the_search(bad_targets):
    with pytest.raises(ValueError, match="目标岗位方向"):
        build_recommendation_candidate(skills_text="Python", target_directions=bad_targets)


@pytest.mark.parametrize("defect", [
    "old", "echo_scope", "echo_reordered", "echo_duplicates", "no_version", "ranking", "classification_order",
    "wrong_matched", "bad_quote", "bad_offset", "city_as_direction", "no_core_evidence",
    "unrelated_on_card", "other_as_aligned", "direction_example_missing", "direction_and_blocked",
    "two_sections", "missing_fit", "unknown_version", "wrong_partition", "extra_skill",
])
def test_active_targets_reject_untrusted_quality_or_scope(defect):
    payload = _quality_payload()
    item = payload["recommendations"][0]
    rows = item["skill_requirements"]
    if defect == "old":
        payload = response_payload()
    elif defect == "echo_scope":
        payload["target_directions"] = ["backend"]
    elif defect == "echo_reordered":
        payload["target_directions"].reverse()
    elif defect == "echo_duplicates":
        payload["target_directions"].append("backend")
    elif defect == "no_version":
        del payload["ranking_version"]
    elif defect == "ranking":
        payload["recommendations"].reverse()
    elif defect == "classification_order":
        rows.reverse()
    elif defect == "wrong_matched":
        rows[0]["matched"] = False
    elif defect == "bad_quote":
        rows[0]["evidence"][0]["text"] = "有相关工作经验"
    elif defect == "bad_offset":
        item["direction_fit"]["evidence"][0]["end"] += 1
    elif defect == "city_as_direction":
        item["direction_fit"]["evidence"] = [{"field": "city", "start": 0, "end": 2, "text": "深圳"}]
    elif defect == "no_core_evidence":
        rows[0]["evidence"] = []
    elif defect == "unrelated_on_card":
        item["direction_fit"] = dict(item["direction_fit"], status="unrelated", detected_directions=["other"])
    elif defect == "other_as_aligned":
        item["direction_fit"]["detected_directions"] = ["other"]
    elif defect == "direction_example_missing":
        payload["direction_excluded"] = []
    elif defect == "direction_and_blocked":
        payload["direction_excluded"][0]["eligibility"]["overall"] = "not_met"
    elif defect == "two_sections":
        bad = payload["direction_excluded"][0]
        bad["eligibility"]["job"]["id"] = bad["job"]["id"] = item["job"]["id"]
    elif defect == "missing_fit":
        del item["direction_fit"]
    elif defect == "unknown_version":
        payload["ranking_version"] = "v999"
    elif defect == "wrong_partition":
        payload["counts"]["met"] = 1
    elif defect == "extra_skill":
        rows.append(dict(rows[0], skill="C++"))
    client = RecommendationApiClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)))
    candidate = build_recommendation_candidate(skills_text="Python", target_directions=["backend", "devops"])
    with pytest.raises(BackendResponseError):
        client.recommend(candidate=candidate)


def test_new_version_without_target_does_not_accept_a_direction_filtered_response():
    candidate = build_recommendation_candidate(skills_text="Python")
    client = RecommendationApiClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=_quality_payload())
    ))
    with pytest.raises(BackendResponseError):
        client.recommend(candidate=candidate)


def test_unrestricted_current_response_reports_its_empty_scope_explicitly():
    payload = response_payload()
    payload.update(ranking_version="direction-core-v1", recommendations=[_quality_item(1, direction="not_requested")],
                   direction_excluded=[], target_directions=[])
    assert AgentRecommendationResponse.model_validate(payload).target_directions == []
    del payload["target_directions"]
    with pytest.raises(ValueError, match="report the target directions"):
        AgentRecommendationResponse.model_validate(payload)


def test_qualification_then_direction_then_core_then_bonus_order():
    payload = _quality_payload()
    payload["recommendations"] = [
        _quality_item(8, direction="uncertain", core="SQL", overall="met"),
        _quality_item(5, core="Python"), _quality_item(4, core="SQL"),
        _quality_item(3, direction="uncertain", core="Python"),
    ]
    payload["direction_excluded"] = []
    payload["counts"].update(evaluated=4, met=1, unknown=3, direction_mismatch=0, returned=4)
    result = AgentRecommendationResponse.model_validate(payload)
    assert [item.job.id for item in result.recommendations] == [8, 5, 4, 3]
    for index in range(3):
        wrong = copy.deepcopy(payload)
        recs = wrong["recommendations"]
        recs[index], recs[index + 1] = recs[index + 1], recs[index]
        with pytest.raises(ValueError, match="order"):
            AgentRecommendationResponse.model_validate(wrong)


def test_absent_category_is_weaker_than_an_evidenced_zero_and_bonus_breaks_core_tie():
    payload = _quality_payload()
    has_core, has_bonus = _quality_item(3, core="SQL"), _quality_item(2, core="SQL")
    no_bonus = _quality_item(1, core="SQL")
    has_core["skill_requirements"][0]["importance"] = "unclassified"  # no bonus
    has_bonus["skill_requirements"][1]["importance"] = "unclassified"  # no core, bonus Python
    no_bonus["skill_requirements"][1]["importance"] = "unclassified"
    no_bonus["skill_requirements"][0]["importance"] = "unclassified"
    payload.update(recommendations=[has_core, has_bonus, no_bonus], direction_excluded=[])
    payload["counts"].update(evaluated=3, unknown=3, direction_mismatch=0, returned=3)
    assert [item.job.id for item in AgentRecommendationResponse.model_validate(payload).recommendations] == [3, 2, 1]
