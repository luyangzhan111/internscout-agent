"""The conservative parser must retain exact evidence and avoid false gates."""

from datetime import datetime

import pytest

from app.eligibility.extractor import extract_conditions, normalize_city
from app.eligibility.contracts import EligibilityProfile
from app.eligibility.evaluator import evaluate_eligibility
from app.schemas.job_response import JobRead


def job(description="", *, title="开发岗位", city="深圳"):
    return JobRead(id=1, title=title, company="Example", city=city,
                   salary=None, description=description, skills=[], source="manual",
                   source_url="https://example.com/jobs/1", published_at=None,
                   created_at=datetime(2026, 1, 1))


def rules(text, dimension):
    return [rule for rule in extract_conditions(job(text)) if rule.dimension == dimension]


@pytest.mark.parametrize("text,years", [
    ("面向2027届毕业生", [2027]), ("2026、2027届与本科及以上", [2026, 2027]),
    ("2026-2028届毕业生", [2026, 2027, 2028]), ("2026, 2027 graduates", [2026, 2027]),
    ("class of 2027", [2027]), ("graduating in 2027", [2027]),
])
def test_graduation_years_and_closed_ranges(text, years):
    result = rules(text, "graduation_year")
    assert len(result) == 1
    assert result[0].kind == "required"
    assert result[0].years == years


@pytest.mark.parametrize("text", [
    "2026年9月至2027年8月毕业", "2027届以后的毕业生", "不接受2027届",
    "应届毕业生", "2027年项目经验的毕业生", "2027-2026届",
    "Graduating between September 2026 and August 2027",
])
def test_ambiguous_graduation_remains_uncertain(text):
    assert all(rule.kind == "uncertain" for rule in rules(text, "graduation_year"))


def test_project_year_alone_does_not_become_graduation():
    assert rules("参与2027年项目建设", "graduation_year") == []


def test_degree_preference_does_not_change_bachelor_requirement():
    result = rules("2026、2027届与本科及以上，硕士优先", "degree")
    assert [(rule.kind, rule.operator, rule.degrees) for rule in result] == [
        ("required", "min", ["bachelor"]), ("preferred", "in", ["master"]),
    ]


@pytest.mark.parametrize("text,operator,degrees,status", [
    ("本科或硕士在读", "in", ["bachelor", "master"], "enrolled"),
    ("已取得硕士学位", "in", ["master"], "completed"),
    ("大专及以上学历", "min", ["associate"], None),
    ("Bachelor's degree or above", "min", ["bachelor"], None),
    ("Currently pursuing a master's degree", "in", ["master"], "enrolled"),
])
def test_degree_levels_and_attainment_status(text, operator, degrees, status):
    result = rules(text, "degree")[0]
    assert result.kind == "required"
    assert result.operator == operator
    assert result.degrees == degrees
    assert result.degree_status == status


@pytest.mark.parametrize("text", ["非本科毕业生", "本科已毕业硕士在读"])
def test_degree_unsupported_scope_is_uncertain(text):
    assert rules(text, "degree")[0].kind == "uncertain"


@pytest.mark.parametrize("text,dimension,operator,minimum,maximum", [
    ("至少2年工作经验", "experience", "min", 24, None),
    ("工作经验不超过6个月", "experience", "max", None, 6),
    ("1-3年工作经验", "experience", "range", 12, 36),
    ("At least 2 years of work experience", "experience", "min", 24, None),
    ("实习至少半年", "internship_duration", "min", 6, None),
    ("实习时长3至6个月", "internship_duration", "range", 3, 6),
    ("实习至少两个月", "internship_duration", "min", 2, None),
    ("实习最多一年", "internship_duration", "max", None, 12),
    ("Internship duration: at least 6 months", "internship_duration", "min", 6, None),
])
def test_duration_units_and_inclusive_bounds(text, dimension, operator, minimum, maximum):
    result = rules(text, dimension)[0]
    assert result.kind == "required"
    assert (result.operator, result.min_months, result.max_months) == (operator, minimum, maximum)


@pytest.mark.parametrize("text", [
    "至少3年相关工作经验", "2年以上Java经验", "至少3年项目经验",
    "3年以上开发经验", "2 years of Python experience", "至少3年实习经验",
    "超过3年工作经验", "工作经验2年", "不要求3年工作经验",
])
def test_domain_experience_and_unsupported_boundaries_are_uncertain(text):
    assert rules(text, "experience")[0].kind == "uncertain"


def test_weekly_days_are_not_internship_months():
    result = rules("实习每周5天", "internship_duration")[0]
    assert result.kind == "uncertain"
    assert result.min_months is None and result.max_months is None


@pytest.mark.parametrize("text,dimension", [
    ("经验不限", "experience"), ("无工作经验要求", "experience"),
    ("No work experience required", "experience"), ("学历不限", "degree"),
    ("毕业届次不限", "graduation_year"), ("实习时长不限", "internship_duration"),
])
def test_unrestricted_has_explicit_evidence(text, dimension):
    result = rules(text, dimension)[0]
    assert (result.kind, result.operator) == ("unrestricted", "any")


@pytest.mark.parametrize("text,dimension", [
    ("2027届优先", "graduation_year"), ("硕士加分", "degree"),
    ("至少3年工作经验优先", "experience"), ("实习至少6个月更佳", "internship_duration"),
])
def test_preference_is_not_a_hard_gate(text, dimension):
    assert rules(text, dimension)[0].kind == "preferred"


def test_structured_multiple_cities_and_conflicting_description_remain_separate():
    result = [rule for rule in extract_conditions(job("工作地点：上海", city="北京、深圳/广州")) if rule.dimension == "city"]
    assert [rule.cities for rule in result] == [["北京", "深圳", "广州"], ["上海"]]


@pytest.mark.parametrize("text,cities", [
    ("工作地点：北京、深圳", ["北京", "深圳"]),
    ("base Shenzhen", ["深圳"]), ("Location: Beijing or Shanghai", ["北京", "上海"]),
])
def test_explicit_city_labels(text, cities):
    result = [rule for rule in rules(text, "city") if rule.evidence[0].field == "description"]
    assert result[0].kind == "required"
    assert result[0].cities == cities


@pytest.mark.parametrize("value,expected", [
    ("北京市", "北京"), (" shenzhen ", "深圳"), ("Xi'an", "西安"),
    ("未知市", None), ("纽约", None), ("全国", None), ("远程", None),
])
def test_only_known_city_aliases_are_normalized(value, expected):
    assert normalize_city(value) == expected


def test_every_quote_uses_exact_unicode_source_offsets():
    current = job("📌 要求：2026、2027届与本科及以上，硕士优先。\n实习至少半年；工作地点：上海", city="北京市")
    extracted = extract_conditions(current)
    assert extracted
    for rule in extracted:
        for evidence in rule.evidence:
            assert getattr(current, evidence.field)[evidence.start:evidence.end] == evidence.text


def test_absent_conditions_have_no_fabricated_evidence():
    result = extract_conditions(job("负责软件设计与测试"))
    assert [rule.dimension for rule in result] == ["city"]


def test_comma_before_preferred_degree_keeps_both_scopes():
    result = rules("必须本科，硕士优先", "degree")
    assert [(rule.kind, rule.degrees) for rule in result] == [
        ("required", ["bachelor"]), ("preferred", ["master"]),
    ]


def test_minimum_phrase_is_not_mistaken_for_strict_less_than():
    result = rules("不少于3年工作经验", "experience")[0]
    assert (result.kind, result.operator, result.min_months) == ("required", "min", 36)


def test_internship_experience_does_not_create_duration_gate():
    assert rules("至少3年实习经验", "internship_duration") == []


@pytest.mark.parametrize("text", ["实习至少一二个月", "实习至少2年半"])
def test_unsupported_compound_duration_does_not_crash_or_shorten(text):
    assert rules(text, "internship_duration")[0].kind == "uncertain"


def test_plain_header_does_not_conflict_with_following_degree():
    result = rules("学历要求：\n本科及以上", "degree")
    assert len(result) == 1
    assert result[0].kind == "required"


def test_remote_work_keeps_location_uncertainty_visible():
    result = rules("支持远程办公", "city")
    assert result[-1].kind == "uncertain"
    assert result[-1].evidence[0].text == "支持远程办公"


@pytest.mark.parametrize("text,kind", [("无经验者优先", "preferred"), ("无经验者勿投", "uncertain")])
def test_no_experience_people_are_not_no_experience_requirement(text, kind):
    result = rules(text, "experience")[0]
    assert result.kind == kind
    assert result.operator == "unknown"


def test_domain_preference_does_not_pollute_unrestricted_work_experience():
    result = rules("工作经验不限，GAN经验优先", "experience")
    assert [(rule.kind, rule.operator) for rule in result] == [
        ("unrestricted", "any"), ("preferred", "unknown"),
    ]
    assert result[1].evidence[0].text == "GAN经验优先"


def test_unrestricted_word_in_a_preference_is_not_a_hard_rule():
    assert rules("工作经验不限者优先", "experience")[0].kind == "preferred"


def test_parenthesized_duration_keeps_explicit_internship_context():
    result = rules("实习生（至少六个月）", "internship_duration")[0]
    assert (result.kind, result.operator, result.min_months) == ("required", "min", 6)
    assert [span.text for span in result.evidence] == ["实习生", "至少六个月"]


def test_duration_is_not_inferred_from_an_unrelated_parenthesis():
    assert rules("平台项目（至少六个月）", "internship_duration") == []


def test_at_least_before_internship_verb():
    result = rules("至少实习6个月", "internship_duration")[0]
    assert (result.kind, result.operator, result.min_months) == ("required", "min", 6)


def test_english_plus_experience_is_explicit_minimum():
    result = rules("2+ years of work experience", "experience")[0]
    assert (result.kind, result.operator, result.min_months) == ("required", "min", 24)


@pytest.mark.parametrize("text", ["博士后", "postgraduate degree", "postdoctoral experience"])
def test_unresolved_english_postgraduate_and_postdoctoral_terms_are_not_guessed(text):
    result = rules(text, "degree")[0]
    assert result.kind == "uncertain"
    assert result.operator == "unknown"
    assert result.evidence[0].text == text


def test_chinese_postgraduate_level_preserves_both_master_and_doctor():
    result = rules("研究生", "degree")[0]
    assert result.kind == "required" and result.operator == "in"
    assert result.degrees == ["master", "doctor"]
    assert result.degree_status is None


def decision(text, *, graduation_year=2027, degree="bachelor", experience=0):
    return evaluate_eligibility(job(text), EligibilityProfile(
        graduation_year=graduation_year, degree=degree, degree_status="completed",
        work_experience_months=experience, acceptable_cities=["深圳"], internship_months=6,
    ))


@pytest.mark.parametrize("year", [2026, 2027])
def test_correlated_cohort_degree_alternatives_do_not_become_independent_gates(year):
    result = decision("2026届本科或2027届硕士。工作经验不限；实习时长不限。",
                      graduation_year=year, degree="master")
    checks = {item.dimension: item for item in result.checks}
    assert checks["graduation_year"].status == "unknown"
    assert checks["degree"].status == "unknown"
    assert result.overall == "unknown"


def test_degree_or_experience_does_not_incorrectly_reject_experienced_bachelor():
    result = decision("2027届；硕士学历或至少3年工作经验；实习时长不限。", experience=60)
    checks = {item.dimension: item for item in result.checks}
    assert checks["degree"].status == "unknown"
    assert checks["experience"].status == "unknown"
    assert result.overall == "unknown"


def test_pure_graduation_year_or_list_with_degree_stays_supported():
    extracted = rules("2026或2027届与本科及以上", "graduation_year")
    assert extracted[0].kind == "required"
    assert extracted[0].years == [2026, 2027]


def test_preference_section_heading_has_evidence_and_does_not_reject_bachelor():
    text = "本科及以上学历。\n加分项：\n硕士学历。"
    extracted = rules(text, "degree")
    assert [rule.kind for rule in extracted] == ["required", "preferred"]
    assert [span.text for span in extracted[1].evidence] == ["加分项：", "硕士学历"]
    result = decision(text)
    assert next(item for item in result.checks if item.dimension == "degree").status == "met"
    assert result.overall != "not_met"


def test_parenthetical_preference_applies_to_preceding_requirement():
    text = "硕士及以上学历（优先）"
    extracted = rules(text, "degree")
    assert len(extracted) == 1
    assert extracted[0].kind == "preferred"
    assert [span.text for span in extracted[0].evidence] == ["硕士及以上学历", "优先"]
    result = decision(text)
    assert next(item for item in result.checks if item.dimension == "degree").status == "unknown"
    assert result.overall != "not_met"


def test_explicit_required_heading_ends_preference_section():
    text = "加分项：\n硕士学历。\n基本要求：\n本科及以上学历。"
    assert [rule.kind for rule in rules(text, "degree")] == ["preferred", "required"]


@pytest.mark.parametrize("text", ["不面向2027届应届生", "应届生招聘范围不含2027届"])
def test_negated_graduation_conditions_cannot_claim_met(text):
    result = decision(text)
    check = next(item for item in result.checks if item.dimension == "graduation_year")
    assert check.status == "unknown"
    assert check.evidence[0].text == text


@pytest.mark.parametrize("text", ["base北京", "based in北京", "岗位base北京"])
def test_base_without_ascii_space_preserves_conflicting_city_evidence(text):
    current = job(text, city="深圳")
    extracted = [rule for rule in extract_conditions(current) if rule.dimension == "city"]
    assert [rule.cities for rule in extracted] == [["深圳"], ["北京"]]
    result = evaluate_eligibility(current, EligibilityProfile(acceptable_cities=["深圳"]))
    check = next(item for item in result.checks if item.dimension == "city")
    assert check.status == "unknown"
    assert [span.text for span in check.evidence] == ["深圳", text]


def test_preference_context_quotes_still_match_exact_source_offsets():
    current = job("📌 本科及以上学历。\n加分项：\n硕士学历（优先）。")
    for rule in extract_conditions(current):
        for span in rule.evidence:
            assert getattr(current, span.field)[span.start:span.end] == span.text


@pytest.mark.parametrize("text,dimension", [
    ("毕业届次不限但不含2027届", "graduation_year"),
    ("学历不限但不招本科", "degree"),
    ("工作经验不限但不接受无经验者", "experience"),
])
def test_unrestricted_with_an_exclusion_is_not_reported_as_no_gate(text, dimension):
    assert rules(text, dimension)[0].kind == "uncertain"
