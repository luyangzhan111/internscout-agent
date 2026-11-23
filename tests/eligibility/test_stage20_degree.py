"""Degree level/state regressions and boundaries independent of held-out jobs."""

from datetime import datetime

import pytest

from app.eligibility.contracts import ConditionRule, EligibilityProfile, EvidenceSpan
from app.eligibility.evaluator import RULES_VERSION, evaluate_eligibility, evaluate_rules
from app.eligibility.extractor import extract_conditions
from app.schemas.job_response import JobRead


def job(text):
    return JobRead(id=1, title="开发实习生", company="测试来源", city="北京", salary=None,
                   description=text, skills=[], source="test", source_url="https://example.com/1",
                   published_at=None, created_at=datetime(2026, 11, 18))


def degree_check(text, **candidate):
    source = job(text)
    result = evaluate_eligibility(source, EligibilityProfile(**candidate))
    assert result.rules_version == "stage23-rules-v1" == RULES_VERSION
    for check in result.checks:
        for evidence in check.evidence:
            assert getattr(source, evidence.field)[evidence.start:evidence.end] == evidence.text
    return next(check for check in result.checks if check.dimension == "degree")


@pytest.mark.parametrize("text", ["在校生", "在读学生", "在校学生", "面向全体在校生", "日常实习：面向全体在校生", "日常实习面向全体在校生", "本岗位面向在读学生", "1、在校生", "本岗位仅限在校生", "Currently enrolled student", "Must be currently enrolled"])
@pytest.mark.parametrize("state,expected", [("enrolled", "met"), ("completed", "not_met"), (None, "unknown")])
def test_general_student_identity_is_not_an_unknown_degree_level(text, state, expected):
    check = degree_check(text, degree_status=state)
    assert check.status == expected
    assert "未限定学历层级" in check.requirement
    if state is None:
        assert check.unknown_reason == "candidate_missing"


@pytest.mark.parametrize("prefix", ["日常实习：面向全体在校生。", "在校生；", "面向全体在校生\n"])
@pytest.mark.parametrize("degree,state,expected", [
    ("bachelor", "enrolled", "not_met"), ("master", "enrolled", "met"),
    ("doctor", "enrolled", "met"), ("master", "completed", "not_met"),
    ("doctor", "completed", "not_met"), ("bachelor", None, "not_met"),
    (None, "completed", "not_met"), (None, "enrolled", "unknown"),
])
def test_general_student_clause_does_not_mask_specific_level_or_state(prefix, degree, state, expected):
    check = degree_check(prefix + "任职要求：硕士及以上学位在读。", degree=degree, degree_status=state)
    assert check.status == expected


@pytest.mark.parametrize("text", [
    "本科及以上学历，在校生。", "仅面向在校生。本科及以上学历。",
    "Currently enrolled student. Bachelor's degree or above.",
])
def test_separate_level_and_state_clauses_combine_without_inventing_a_degree(text):
    assert degree_check(text, degree="bachelor", degree_status="enrolled").status == "met"
    assert degree_check(text, degree="master", degree_status="completed").status == "not_met"


def test_unparsed_additional_level_does_not_hide_an_independent_clear_failure():
    text = "硕士及以上学历在读。研究生专业说明需确认。"
    assert degree_check(text, degree="bachelor", degree_status="enrolled").status == "not_met"
    assert degree_check(text, degree="master", degree_status="enrolled").status == "unknown"


@pytest.mark.parametrize("text", [
    "2026届在校生。", "计算机、软件工程或相关专业在校生。", "计算机、人工智能或相关专业在读，本科及以上。",
])
def test_student_identity_survives_cohort_or_professional_prefix(text):
    assert degree_check(text, degree="bachelor", degree_status="enrolled").status == "met"
    assert degree_check(text, degree="doctor", degree_status="completed").status == "not_met"


@pytest.mark.parametrize("text", ["在读研究生。", "研究生在读。", "计算机或相关专业在读研究生；研究生导师知情且同意。"])
@pytest.mark.parametrize("degree,state,expected", [
    ("bachelor", "enrolled", "not_met"), ("master", "enrolled", "met"), ("doctor", "enrolled", "met"),
    ("master", "completed", "not_met"), ("doctor", "completed", "not_met"),
])
def test_explicit_postgraduate_student_is_master_or_doctor_and_enrolled(text, degree, state, expected):
    assert degree_check(text, degree=degree, degree_status=state).status == expected


@pytest.mark.parametrize("text", [
    "硕士及以上学历或3年以上工作经验。",
    "硕士及以上学历，或3年以上工作经验。",
    "硕士及以上学历；或具有同等工作经验。",
    "硕士及以上学历，或者有同等项目经验。",
    "硕士及以上学历。学历可放宽。",
    "硕士及以上学历。学历不作要求。",
    "硕士及以上学历。非本科毕业生。",
    "硕士及以上学历。本科已毕业硕士在读。",
    "硕士在读。已取得硕士学位。",
    "学历不限；硕士及以上学历。",
    "在读研究生或社会人士。",
    "硕士及以上学历。学历不限定。",
])
def test_alternatives_waivers_negation_and_conflicting_scope_stay_unknown(text):
    assert degree_check(text, degree="bachelor", degree_status="enrolled").status == "unknown"


@pytest.mark.parametrize("text", ["与在校生协作完成平台建设。", "负责在读学生的培训工作。", "向在校生提供咨询。"])
def test_student_mentions_in_responsibilities_are_not_applicant_state_gates(text):
    check = degree_check(text, degree="bachelor", degree_status="completed")
    assert check.status == "unknown"


@pytest.mark.parametrize("text", ["有指导研究生经验。", "团队招收研究生。", "与在校生合作。", "研究生导师知情且同意。", "研究生背景优先。"])
def test_advisors_colleagues_and_preferred_background_never_set_applicant_degree(text):
    assert degree_check(text, degree="bachelor", degree_status="completed").status == "unknown"
    assert not any(r.kind == "required" for r in extract_conditions(job(text)) if r.dimension == "degree")


@pytest.mark.parametrize("text", ["在校生（非必须）。", "硕士在读（非必须）。", "在校生，非必须。", "硕士在读非必须。"])
def test_optional_degree_or_student_status_is_not_a_hard_filter(text):
    assert degree_check(text, degree="bachelor", degree_status="completed").status == "unknown"


def test_state_preference_never_rejects_another_state():
    check = degree_check("加分项：\n在校生。", degree="master", degree_status="completed")
    assert check.status == "unknown"
    assert check.unknown_reason == "source_unspecified"
    assert check.notes


@pytest.mark.parametrize("operator,degrees,state", [("any", [], None), ("any", ["master"], "enrolled"), ("unknown", [], "enrolled"), ("in", [], "enrolled")])
def test_only_the_precise_state_only_rule_shape_is_supported(operator, degrees, state):
    source = job("在校生")
    condition = ConditionRule(dimension="degree", kind="required", operator=operator, degrees=degrees,
                              degree_status=state, evidence=[EvidenceSpan(field="description", text="在校生", start=0, end=3)])
    result = evaluate_rules(source, EligibilityProfile(degree="bachelor", degree_status="completed"), [condition])
    assert next(c for c in result.checks if c.dimension == "degree").status == "unknown"


def test_unverified_evidence_cannot_support_a_hard_failure():
    source = job("硕士在读；其他说明")
    hard = ConditionRule(dimension="degree", kind="required", operator="min", degrees=["master"], degree_status="enrolled",
                         evidence=[EvidenceSpan(field="description", text="硕士在读", start=0, end=4)])
    bad = ConditionRule(dimension="degree", kind="uncertain", operator="unknown",
                        evidence=[EvidenceSpan(field="description", text="伪造学历", start=0, end=4)])
    result = evaluate_rules(source, EligibilityProfile(degree="bachelor", degree_status="enrolled"), [hard, bad])
    assert next(c for c in result.checks if c.dimension == "degree").status == "unknown"


@pytest.mark.parametrize("year,expected", [(2027, "not_met"), (2028, "met"), (2029, "met"), (None, "unknown")])
def test_explicit_inclusive_graduation_lower_bound(year, expected):
    result = evaluate_eligibility(job("2028届及以后本科及以上学历在读。"), EligibilityProfile(
        graduation_year=year, degree="bachelor", degree_status="enrolled"))
    check = next(c for c in result.checks if c.dimension == "graduation_year")
    assert check.status == expected
    assert "2028届及以后" in check.requirement
    assert next(c for c in result.checks if c.dimension == "degree").status == "met"


@pytest.mark.parametrize("text", ["2028届以后的毕业生。", "2027、2028届及以后毕业生。", "2028届及以后或2027届硕士。", "不接受2028届及以后。", "2028年9月至2029年8月毕业。"])
def test_noninclusive_ambiguous_or_date_graduation_scope_remains_unknown(text):
    result = evaluate_eligibility(job(text), EligibilityProfile(graduation_year=2028))
    assert next(c for c in result.checks if c.dimension == "graduation_year").status == "unknown"


def test_preferred_inclusive_year_bound_is_not_a_hard_filter():
    result = evaluate_eligibility(job("2028届及以后优先。"), EligibilityProfile(graduation_year=2027))
    assert next(c for c in result.checks if c.dimension == "graduation_year").status == "unknown"
