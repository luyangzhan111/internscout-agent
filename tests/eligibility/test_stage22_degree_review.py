"""Independent source-level checks for postgraduate ranges and scope boundaries.

These synthetic descriptions are separate from the new Stage22 holdout. They
test candidate-facing meaning, rather than implementation helper behavior.
"""

from datetime import datetime

import pytest

from app.eligibility.contracts import EligibilityProfile
from app.eligibility.evaluator import evaluate_eligibility
from app.eligibility.extractor import extract_conditions
from app.schemas.job_response import JobRead


def source_job(description):
    return JobRead(id=1, title="开发实习岗位", company="测试来源", city="北京", salary=None,
                   description=description, skills=[], source="manual",
                   source_url="https://careers.company.test/jobs/review",
                   published_at=None, created_at=datetime(2026, 11, 18))


def degree(description, degree="master", state="enrolled"):
    job = source_job(description)
    result = evaluate_eligibility(job, EligibilityProfile(degree=degree, degree_status=state))
    for check in result.checks:
        for quote in check.evidence:
            assert getattr(job, quote.field)[quote.start:quote.end] == quote.text
    check = next(check for check in result.checks if check.dimension == "degree")
    if check.status == "unknown":
        assert check.unknown_reason and check.next_step.strip()
    return check


@pytest.mark.parametrize("description", [
    "在读研究生。", "研究生/博士生在读。", "研究生／博士生在读。",
    "硕士研究生或博士研究生在读。", "硕博在读。", "研究生，博士生在读。",
])
@pytest.mark.parametrize("candidate,state,expected", [
    ("master", "enrolled", "met"), ("doctor", "enrolled", "met"),
    ("bachelor", "enrolled", "not_met"), ("master", "completed", "not_met"),
    ("doctor", None, "unknown"),
])
def test_postgraduate_student_ranges_accept_both_levels_without_dropping_state(description, candidate, state, expected):
    assert degree(description, candidate, state).status == expected


@pytest.mark.parametrize("description", [
    "在读本科生或研究生。", "本科生、研究生在读。", "在读本科生，研究生。",
    "计算机或相关专业本科或研究生在读。",
])
@pytest.mark.parametrize("candidate", ["bachelor", "master", "doctor"])
def test_shared_state_and_professional_subject_or_leave_the_full_degree_list(description, candidate):
    assert degree(description, candidate).status == "met"
    assert degree(description, candidate, "completed").status == "not_met"


@pytest.mark.parametrize("description,candidate,expected", [
    ("硕士研究生在读。", "master", "met"),
    ("硕士研究生在读。", "doctor", "unknown"),
    ("博士研究生在读。", "master", "not_met"),
    ("博士研究生在读。", "doctor", "met"),
    ("研究生及以上学历。", "master", "met"),
    ("研究生及以上学历。", "doctor", "met"),
    ("研究生及以上学历。", "bachelor", "not_met"),
])
def test_explicit_degree_qualifiers_do_not_gain_an_unstated_sibling_level(description, candidate, expected):
    state = "enrolled" if "在读" in description else "completed"
    assert degree(description, candidate, state).status == expected


@pytest.mark.parametrize("description", [
    "研究生在读或社会人士。", "研究生在读/社会人士。",
    "研究生在读／同等项目经验。", "研究生在读或具有同等项目经验。",
    "本科已取得或研究生在读。", "本科毕业或硕士在读。",
    "硕士及以上/本科在读。", "硕士及以下/博士在读。",
    "硕士在读或研究生。", "硕博连读。",
    "研究生学历不作硬性要求。", "研究生学历或优秀者可放宽。",
    "不接受研究生。", "非硕士研究生。",
])
@pytest.mark.parametrize("candidate,state", [("bachelor", "completed"), ("master", "completed")])
def test_alternative_identities_mixed_states_or_waivers_are_never_false_hard_blocks(description, candidate, state):
    assert degree(description, candidate, state).status == "unknown"


@pytest.mark.parametrize("description", [
    "研究生优先。", "研究生在读（优先）。", "硕博在读，非必须。",
    "加分项：\n研究生学历。",
])
def test_postgraduate_preferences_are_not_required_gates(description):
    assert degree(description, "bachelor", "completed").status == "unknown"
    rules = [rule for rule in extract_conditions(source_job(description)) if rule.dimension == "degree"]
    assert not any(rule.kind == "required" for rule in rules)


@pytest.mark.parametrize("description", [
    "研究生导师知情且同意。", "研究生导师同意实习。",
    "团队招收研究生。", "与研究生同事协作。", "负责指导研究生。",
    "具备培养研究生经验。", "面向研究生的服务平台研发。",
])
def test_non_applicant_student_mentions_do_not_assert_a_candidate_degree(description):
    assert degree(description, "bachelor", "completed").status == "unknown"
    assert not any(rule.kind == "required" for rule in extract_conditions(source_job(description))
                   if rule.dimension == "degree")


def test_comma_before_an_advisor_does_not_erase_an_independent_applicant_requirement():
    description = "学历要求：本科，研究生导师知情且同意。"
    assert degree(description, "bachelor", "completed").status == "met"
    assert degree(description, "associate", "completed").status == "not_met"
    rules = [rule for rule in extract_conditions(source_job(description))
             if rule.dimension == "degree" and rule.kind == "required"]
    assert rules and all(rule.degrees == ["bachelor"] for rule in rules)


def test_comma_before_a_parenthesized_preference_does_not_expand_the_required_degree_set():
    description = "学历要求：本科，研究生（优先）。"
    rules = [rule for rule in extract_conditions(source_job(description)) if rule.dimension == "degree"]
    required = [rule for rule in rules if rule.kind == "required"]
    assert required and all(rule.degrees == ["bachelor"] for rule in required)
    assert any(rule.kind == "preferred" and {"master", "doctor"}.issubset(rule.degrees) for rule in rules)
    assert degree(description, "associate", "completed").status == "not_met"


@pytest.mark.parametrize("requirement", [
    "研究生/博士生在读。", "本科，研究生在读。", "计算机或相关专业研究生在读。",
    "研究生优先。",
])
def test_degree_only_range_changes_do_not_modify_the_other_four_condition_checks(requirement):
    prefix = "2027届；工作经验不限；工作地点深圳；实习至少6个月；"
    candidate = EligibilityProfile(graduation_year=2027, degree="master", degree_status="enrolled",
                                   work_experience_months=0, acceptable_cities=["深圳"], internship_months=6)
    before = evaluate_eligibility(source_job(prefix), candidate)
    after = evaluate_eligibility(source_job(prefix + requirement), candidate)
    old = [check.model_dump() for check in before.checks if check.dimension != "degree"]
    new = [check.model_dump() for check in after.checks if check.dimension != "degree"]
    assert old == new
