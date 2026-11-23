"""Development checks for geographic scope; no real-model or new-holdout calls."""

from datetime import datetime
import json
from pathlib import Path

import pytest

from app.eligibility.contracts import EligibilityProfile
from app.eligibility.evaluator import _evaluate_dimension
from app.eligibility.extractor import extract_conditions
from app.eligibility.work_location import evaluate_work_location
from app.schemas.job_response import JobRead
from tests.evaluation.recruitment_corpus import REQUIRES_RECORDED_CORPUS


def job(description, *, city="上海", title="开发实习生"):
    return JobRead(id=1, title=title, company="合成测试主体", city=city,
                   salary=None, description=description, skills=[], source="synthetic",
                   source_url="https://example.com/jobs/1", status="active",
                   published_at=None, created_at=datetime(2026, 11, 18))


def baseline(source, profile):
    rules = [rule for rule in extract_conditions(source) if rule.dimension == "city"]
    return _evaluate_dimension(source, profile, "city", rules)


def assess(source, cities):
    profile = EligibilityProfile(acceptable_cities=cities)
    original = baseline(source, profile)
    before = original.model_dump()
    result = evaluate_work_location(source, profile, original)
    assert original.model_dump() == before, "The function must not mutate the baseline check."
    for span in result.evidence:
        assert getattr(source, span.field)[span.start:span.end] == span.text
        assert span.end - span.start == len(span.text)
    if result.status == "unknown":
        assert result.unknown_reason
        assert result.next_step.strip()
    else:
        assert result.unknown_reason is None
        assert result.next_step == ""
    return original, result


@pytest.mark.parametrize("text", [
    "工作地点：上海；熟悉Python。",
    "组织线上线下结合的技术活动。",
    "负责线上线下结合的课程与培训活动。",
    "开展线上线下结合，组织课程活动。",
    "需具备远程办公经验。",
    "与远程办公团队协作。",
    "对接全远程团队的业务。",
    "支持远程调试和数据部署。",
    "开发不支持远程办公功能的客户端。",
    "Hybrid working experience preferred.",
    "Work with a remote team.",
    "创作视觉元素，包括但不限于新产品视觉系统、运营物料、线上线下宣传物料、图标、插图、布局和动画。",
    "制作仅限会员使用的线上线下宣传物料。",
    "负责为全球客户设计远程办公解决方案。",
    "负责支持全球客户的远程办公需求。",
])
@pytest.mark.parametrize("cities", [["北京"], ["上海"], [], None])
def test_no_current_job_arrangement_is_an_exact_noop(text, cities):
    original, result = assess(job(text), cities)
    assert result is original
    assert result.model_dump() == original.model_dump()


@pytest.mark.parametrize("text", [
    "线上线下结合，实习周期3–6个月。",
    "实习安排：线上线下结合；每周投入20–30小时。",
    "本岗位采用混合办公。",
    "Hybrid internship with our research group.",
])
def test_hybrid_outside_office_city_is_unknown(text):
    original, result = assess(job(text), ["北京", "深圳", "杭州"])
    assert original.status == "not_met"
    assert result.status == "unknown"
    assert result.unknown_reason == "interpretation_uncertain"
    assert any(span.field == "description" for span in result.evidence)
    assert "异地" in result.reason


@pytest.mark.parametrize("cities", [["上海市"], []])
def test_hybrid_geographic_match_does_not_claim_attendance_is_verified(cities):
    _, result = assess(job("实习安排：线上线下结合。"), cities)
    assert result.status == "met"
    assert "尚未额外核实" in result.reason
    assert any("到岗频次" in note and "工作许可" in note for note in result.notes)


@pytest.mark.parametrize("cities,category", [(None, "candidate_missing"), (["火星"], "interpretation_uncertain")])
def test_hybrid_missing_or_unrecognized_candidate_city_stays_unknown(cities, category):
    _, result = assess(job("线上线下结合。"), cities)
    assert result.status == "unknown"
    assert result.unknown_reason == category


@pytest.mark.parametrize("text", [
    "本岗位必须到岗办公，不支持远程办公。",
    "工作形式：线下；必须到岗。",
    "每周必须到岗2天，其余时间可远程办公。",
    "线上线下结合，但不支持异地远程办公。",
    "线上线下结合，不支持全远程办公。",
    "Must work on-site.",
])
def test_explicit_onsite_or_local_requirement_is_still_a_hard_geographic_filter(text):
    _, outside = assess(job(text), ["北京"])
    _, local = assess(job(text), ["上海"])
    assert outside.status == "not_met"
    assert local.status == "met"


@pytest.mark.parametrize("text", [
    "远程办公仅限北京或上海。",
    "远程仅限北京或上海。",
    "仅限北京、上海远程办公。",
    "支持异地远程办公，远程地域仅限北京/上海。",
    "支持北京、上海异地远程办公。",
    "可在北京或上海远程办公。",
    "远程办公必须居住在北京或上海。",
    "只支持北京或上海本地远程办公。",
    "线上线下结合，仅限北京或上海。",
])
def test_remote_cities_are_explicit_and_enforced(text):
    _, accepted = assess(job(text, city="深圳"), ["北京"])
    _, rejected = assess(job(text, city="深圳"), ["杭州"])
    assert accepted.status == "met"
    assert rejected.status == "not_met"


@pytest.mark.parametrize("text", [
    "全远程办公。",
    "支持远程办公。",
    "可异地远程办公。",
    "Fully remote work.",
])
def test_remote_without_comparable_scope_is_not_global_permission(text):
    _, result = assess(job(text), ["北京"])
    assert result.status == "unknown"
    assert result.unknown_reason == "interpretation_uncertain"


@pytest.mark.parametrize("text", [
    "远程办公仅限美国境内。",
    "全远程办公（仅限美国）。",
    "全远程办公，仅限火星。",
    "Remote work within the United States.",
])
@pytest.mark.parametrize("cities", [["上海"], ["北京"], []])
def test_unrecognized_remote_country_or_region_is_not_relaxed(text, cities):
    _, result = assess(job(text), cities)
    assert result.status == "unknown"


@pytest.mark.parametrize("text", [
    "允许异地远程办公，工作地点不限。",
    "支持全球异地远程工作。",
    "Remote work from anywhere.",
])
@pytest.mark.parametrize("cities", [["北京"], [], None])
def test_explicit_unrestricted_remote_relaxes_geography_only(text, cities):
    _, result = assess(job(text), cities)
    assert result.status == "met"
    assert "地理" in result.reason
    assert any("工作许可" in note for note in result.notes)


@pytest.mark.parametrize("text", ["全国远程办公。", "支持中国大陆异地远程工作。"])
def test_domestic_remote_has_a_comparable_bounded_scope(text):
    _, accepted = assess(job(text), ["北京", "深圳"])
    _, unresolved = assess(job(text), ["伦敦"])
    _, missing = assess(job(text), None)
    assert accepted.status == "met"
    assert unresolved.status == "unknown"
    assert missing.unknown_reason == "candidate_missing"


@pytest.mark.parametrize("text", [
    "可远程办公；不支持远程办公。",
    "本岗位全远程办公；每周必须到岗2天。",
    "允许异地远程办公；不支持异地远程办公。",
    "远程办公仅限北京；远程办公仅限上海。",
    "支持全球远程办公；远程办公仅限北京。",
])
def test_genuine_incompatible_arrangements_need_confirmation(text):
    _, result = assess(job(text), ["北京"])
    assert result.status == "unknown"
    assert result.unknown_reason == "requirements_conflict"


@pytest.mark.parametrize("text", [
    "工作地点：上海线下或北京远程办公。",
    "可选上海线下办公或北京远程办公。",
    "可选择上海到岗办公或北京远程工作。",
    "可选北京远程办公或上海线下办公。",
])
def test_explicit_alternative_cities_are_options_not_conflicts(text):
    _, office = assess(job(text), ["上海"])
    _, remote = assess(job(text), ["北京"])
    _, outside = assess(job(text), ["杭州"])
    assert office.status == "met"
    assert remote.status == "met"
    assert outside.status == "not_met"


def test_explicit_onsite_location_conflict_remains_visible():
    _, result = assess(job("必须在北京到岗办公。", city="上海"), ["上海"])
    assert result.status == "unknown"
    assert result.unknown_reason == "requirements_conflict"


@pytest.mark.parametrize("city,text", [
    ("", "线上线下结合。"),
    ("火星", "混合办公。"),
    ("上海/伦敦", "线上线下结合。"),
    ("上海", "工作地点伦敦；混合办公。"),
    ("上海", "工作地点伦敦远程办公。"),
])
@pytest.mark.parametrize("cities", [[], ["上海"]])
def test_work_arrangement_does_not_erase_an_unrecognized_workplace(city, text, cities):
    _, result = assess(job(text, city=city), cities)
    assert result.status == "unknown"


def test_required_onsite_and_disjoint_remote_regions_need_confirmation():
    _, result = assess(job("每周必须到岗2天；远程办公仅限北京。"), ["上海"])
    assert result.status == "unknown"
    assert result.unknown_reason == "requirements_conflict"


@pytest.mark.parametrize("text", [
    "工作地点：上海线下或全国远程办公。",
    "可选上海到岗或全球远程办公。",
])
def test_optional_office_or_explicit_broader_remote_scope_is_not_a_conflict(text):
    _, result = assess(job(text), ["北京"])
    assert result.status == "met"


def test_current_snapshot_evidence_covers_unicode_offsets_and_title_mode():
    source = job("🧪研究岗位\n  工作地点：上海；其他条件详见原文。", title="研究实习生（线上线下结合）")
    _, result = assess(source, ["北京"])
    assert result.status == "unknown"
    assert any(span.field == "title" and "线上线下结合" in span.text for span in result.evidence)
    assert any(span.field == "city" and span.text == "上海" for span in result.evidence)


@REQUIRES_RECORDED_CORPUS
def test_six_stage22_development_false_blocks_are_recovered_to_unknown():
    jobs = json.loads((Path(__file__).resolve().parents[2] / "data/real_jobs/stage22/jobs.json").read_text(encoding="utf-8"))
    selected = [item for item in jobs if "线上线下结合" in item["description"]]
    assert len(selected) == 6
    for item in selected:
        source = job(item["description"], city=item["city"], title=item["title"])
        original, result = assess(source, ["北京", "深圳", "杭州"])
        assert original.status == "not_met"
        assert result.status == "unknown"
        assert result.unknown_reason == "interpretation_uncertain"
        assert any("线上线下结合" in span.text for span in result.evidence)


@pytest.mark.parametrize("text", [
    "不支持全国远程办公。", "不接受全球远程办公。",
    "不允许中国大陆远程工作。", "不支持在全国范围内远程办公。",
    "不支持北京远程办公。", "不接受深圳市远程工作。",
])
def test_denied_remote_regions_never_become_positive_permission(text):
    _, outside = assess(job(text), ["北京"])
    _, office = assess(job(text), ["上海"])
    assert outside.status == "not_met"
    assert office.status == "met"


@pytest.mark.parametrize("text", [
    "全远程办公，主要服务全球客户。",
    "本岗支持远程办公，负责全国客户的技术支持。",
    "全国客户的技术支持岗位，可远程办公。",
    "与全球团队协作，支持远程办公。",
    "本岗支持远程办公，客户覆盖仅限北京。",
])
def test_customer_or_team_coverage_does_not_define_remote_candidate_scope(text):
    _, outside = assess(job(text), ["北京"])
    assert outside.status == "unknown"
    assert outside.unknown_reason == "interpretation_uncertain"


@pytest.mark.parametrize("text", [
    "支持全国远程办公，但须每周到上海办公一天。",
    "本岗可远程工作，要求每月前往上海工作两天。",
    "混合办公，需要每周在上海办公两天。",
])
def test_explicit_travel_to_office_remains_a_geographic_constraint(text):
    _, outside = assess(job(text), ["北京"])
    _, office = assess(job(text), ["上海"])
    assert outside.status == "not_met"
    assert office.status == "met"
