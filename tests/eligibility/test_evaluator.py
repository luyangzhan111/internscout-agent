"""Synthetic decision checks; these do not estimate real-world accuracy."""

from datetime import datetime, timedelta

import pytest

from app.eligibility.contracts import ConditionCheck, ConditionRule, EligibilityProfile, EvidenceSpan
from app.eligibility.evaluator import DIMENSIONS, evaluate_eligibility, evaluate_rules, source_fingerprint
from app.schemas.job_response import JobRead


def make_job(description="2027届；本科及以上；工作经验不限；工作地点深圳；实习至少6个月", **overrides):
    values = dict(id=1, title="开发实习生", company="测试公司", city="深圳",
                  salary=None, description=description, skills=[], source="test",
                  source_url="https://example.com/jobs/1", status="active",
                  published_at=None, created_at=datetime(2026, 11, 12))
    values.update(overrides)
    return JobRead(**values)


def rule(job, dimension, quote=None, *, field="description", kind="required", operator="in", **values):
    source = getattr(job, field)
    quote = source if quote is None else quote
    start = source.index(quote)
    return ConditionRule(dimension=dimension, kind=kind, operator=operator,
                         evidence=[EvidenceSpan(field=field, text=quote, start=start, end=start + len(quote))],
                         **values)


def check(job, profile, rules, dimension):
    result = evaluate_rules(job, profile, rules)
    assert len(result.checks) == 5
    assert tuple(item.dimension for item in result.checks) == DIMENSIONS
    for item in result.checks:
        if item.status == "unknown":
            assert item.unknown_reason in {
                "candidate_missing", "source_unspecified", "interpretation_uncertain", "requirements_conflict",
            }
            assert item.next_step.strip()
        else:
            assert item.unknown_reason is None
            assert item.next_step == ""
    return next(item for item in result.checks if item.dimension == dimension)


def full_rules(job):
    return [
        rule(job, "graduation_year", "2027届", years=[2027]),
        rule(job, "degree", "本科及以上", operator="min", degrees=["bachelor"]),
        rule(job, "experience", "工作经验不限", kind="unrestricted", operator="any"),
        rule(job, "city", "工作地点深圳", cities=["深圳"]),
        rule(job, "internship_duration", "实习至少6个月", operator="min", min_months=6),
    ]


def test_all_five_explicit_comparable_conditions_can_pass():
    job = make_job()
    profile = EligibilityProfile(graduation_year=2027, degree="bachelor",
                                 degree_status="completed", acceptable_cities=["深圳市"], internship_months=6)
    result = evaluate_rules(job, profile, full_rules(job))
    assert result.overall == "met"
    assert all(item.status == "met" for item in result.checks)
    assert all(item.unknown_reason is None and item.next_step == "" for item in result.checks)
    assert result.blocking_reasons == []
    assert len(result.source_fingerprint) == 64
    assert result.rules_version


def test_missing_rules_always_return_five_unknown_checks():
    result = evaluate_rules(make_job(), EligibilityProfile(), [])
    assert len(result.checks) == 5
    assert result.overall == "unknown"
    assert all(item.status == "unknown" and not item.evidence for item in result.checks)
    assert all(item.unknown_reason == "source_unspecified" and "招聘方" in item.next_step for item in result.checks)


@pytest.mark.parametrize("dimension,values,profile", [
    ("graduation_year", {"years": [2026]}, {"graduation_year": 2027}),
    ("degree", {"operator": "min", "degrees": ["master"]}, {"degree": "bachelor"}),
    ("experience", {"operator": "min", "min_months": 24}, {"work_experience_months": 0}),
    ("city", {"cities": ["北京"]}, {"acceptable_cities": ["深圳"]}),
    ("internship_duration", {"operator": "min", "min_months": 6}, {"internship_months": 3}),
])
def test_clear_failure_in_each_dimension_overrides_other_unknowns(dimension, values, profile):
    job = make_job("明确要求")
    result = evaluate_rules(job, EligibilityProfile(**profile), [rule(job, dimension, **values)])
    assert result.overall == "not_met"
    assert len(result.checks) == 5
    assert next(item for item in result.checks if item.dimension == dimension).status == "not_met"
    assert len(result.blocking_reasons) == 1


@pytest.mark.parametrize("dimension,values,profile", [
    ("graduation_year", {"years": [2026, 2027]}, {"graduation_year": 2027}),
    ("degree", {"operator": "in", "degrees": ["bachelor", "master"]}, {"degree": "master", "degree_status": "completed"}),
    ("degree", {"operator": "min", "degrees": ["associate"]}, {"degree": "doctor", "degree_status": "completed"}),
    ("experience", {"operator": "min", "min_months": 0}, {"work_experience_months": 0}),
    ("experience", {"operator": "max", "max_months": 24}, {"work_experience_months": 24}),
    ("experience", {"operator": "range", "min_months": 12, "max_months": 24}, {"work_experience_months": 12}),
    ("city", {"cities": ["北京", "深圳市"]}, {"acceptable_cities": ["深圳"]}),
    ("city", {"cities": ["北京"]}, {"acceptable_cities": []}),
    ("internship_duration", {"operator": "min", "min_months": 6}, {"internship_months": 6}),
    ("internship_duration", {"operator": "range", "min_months": 3, "max_months": 6}, {"internship_months": 6}),
])
def test_inclusive_boundaries_enumerations_and_explicit_unlimited_city_pass(dimension, values, profile):
    job = make_job("明确要求")
    assert check(job, EligibilityProfile(**profile), [rule(job, dimension, **values)], dimension).status == "met"


@pytest.mark.parametrize("dimension,values", [
    ("graduation_year", {"years": [2027]}),
    ("degree", {"operator": "min", "degrees": ["bachelor"]}),
    ("experience", {"operator": "min", "min_months": 0}),
    ("city", {"cities": ["深圳"]}),
    ("internship_duration", {"operator": "min", "min_months": 0}),
])
def test_missing_candidate_is_not_a_zero_or_an_unrestricted_choice(dimension, values):
    job = make_job("明确要求")
    item = check(job, EligibilityProfile(), [rule(job, dimension, **values)], dimension)
    assert item.status == "unknown"
    assert "未填写" in item.reason
    assert item.unknown_reason == "candidate_missing"
    assert "补充" in item.next_step


@pytest.mark.parametrize("dimension", DIMENSIONS)
def test_explicit_source_unrestricted_passes_even_without_candidate(dimension):
    job = make_job("不限")
    item = check(job, EligibilityProfile(), [rule(job, dimension, kind="unrestricted", operator="any")], dimension)
    assert item.status == "met"
    assert item.evidence[0].text == "不限"


def test_preferred_rule_never_rejects_candidate_or_provides_hard_pass_alone():
    job = make_job("本科及以上，硕士优先")
    preference = rule(job, "degree", "硕士优先", kind="preferred", degrees=["master"])
    profile = EligibilityProfile(degree="bachelor", degree_status="completed")
    only = check(job, profile, [preference], "degree")
    assert only.status == "unknown" and only.notes
    assert only.unknown_reason == "source_unspecified"
    hard = rule(job, "degree", "本科及以上", operator="min", degrees=["bachelor"])
    both = check(job, profile, [hard, preference], "degree")
    assert both.status == "met" and both.notes


@pytest.mark.parametrize("dimension,first,second,profile", [
    ("graduation_year", {"years": [2026]}, {"years": [2027]}, {"graduation_year": 2027}),
    ("degree", {"degrees": ["bachelor"]}, {"degrees": ["master"]}, {"degree": "master"}),
    ("degree", {"degrees": ["bachelor"], "degree_status": "completed"},
     {"degrees": ["bachelor"], "degree_status": "enrolled"}, {"degree": "bachelor", "degree_status": "enrolled"}),
    ("experience", {"operator": "min", "min_months": 24}, {"operator": "max", "max_months": 12}, {"work_experience_months": 24}),
    ("internship_duration", {"operator": "min", "min_months": 6}, {"operator": "max", "max_months": 3}, {"internship_months": 6}),
    ("city", {"cities": ["北京"]}, {"cities": ["深圳"]}, {"acceptable_cities": ["深圳"]}),
])
def test_contradictory_required_rules_are_unknown(dimension, first, second, profile):
    job = make_job("条件甲；条件乙")
    rules = [rule(job, dimension, "条件甲", **first), rule(job, dimension, "条件乙", **second)]
    item = check(job, EligibilityProfile(**profile), rules, dimension)
    assert item.status == "unknown"
    assert "冲突" in item.reason
    assert item.unknown_reason == "requirements_conflict"
    assert "招聘方" in item.next_step


def test_city_field_and_description_conflict_is_unknown_even_with_unlimited_candidate():
    job = make_job("工作地点北京", city="深圳")
    rules = [rule(job, "city", field="city", cities=["深圳"]), rule(job, "city", cities=["北京"])]
    assert check(job, EligibilityProfile(acceptable_cities=[]), rules, "city").status == "unknown"


def test_nonconflicting_multiple_rules_use_their_common_range():
    job = make_job("经验至少1年，最多2年")
    rules = [rule(job, "experience", "至少1年", operator="min", min_months=12),
             rule(job, "experience", "最多2年", operator="max", max_months=24)]
    assert check(job, EligibilityProfile(work_experience_months=18), rules, "experience").status == "met"
    assert check(job, EligibilityProfile(work_experience_months=30), rules, "experience").status == "not_met"


@pytest.mark.parametrize("required_state,candidate_state,expected", [
    ("completed", "enrolled", "not_met"), ("completed", "completed", "met"),
    ("enrolled", None, "unknown"), ("enrolled", "completed", "not_met"),
    ("enrolled", "enrolled", "met"), (None, "enrolled", "unknown"),
    (None, None, "unknown"), (None, "completed", "met"),
])
def test_degree_level_and_attainment_are_compared_separately(required_state, candidate_state, expected):
    job = make_job("本科条件")
    requirement = rule(job, "degree", degrees=["bachelor"], degree_status=required_state)
    profile = EligibilityProfile(degree="bachelor", degree_status=candidate_state)
    item = check(job, profile, [requirement], "degree")
    assert item.status == expected
    if expected == "unknown":
        assert item.unknown_reason == ("candidate_missing" if candidate_state is None else "interpretation_uncertain")
        assert ("补充" if candidate_state is None else "招聘方") in item.next_step


@pytest.mark.parametrize("cities,candidate", [(["未知城"], ["深圳"]), (["深圳"], ["未知城"]), (["深圳"], ["深圳", "未知城"])])
def test_unrecognized_city_does_not_produce_a_definite_decision(cities, candidate):
    job = make_job("城市条件")
    item = check(job, EligibilityProfile(acceptable_cities=candidate), [rule(job, "city", cities=cities)], "city")
    assert item.status == "unknown"
    assert item.unknown_reason == "interpretation_uncertain"


def test_uncertain_clause_blocks_pass_and_keeps_valid_source_evidence():
    job = make_job("本科及以上，相关专业经验")
    rules = [rule(job, "degree", "本科及以上", operator="min", degrees=["bachelor"]),
             rule(job, "degree", "相关专业经验", kind="uncertain", operator="unknown", note="需确认原意")]
    item = check(job, EligibilityProfile(degree="master"), rules, "degree")
    assert item.status == "unknown"
    assert len(item.evidence) == 2
    assert "需确认原意" in item.notes
    assert item.unknown_reason == "interpretation_uncertain"


@pytest.mark.parametrize("mutation", ["wrong_text", "wrong_field", "missing", "wrong_offset"])
def test_invalid_citations_cannot_pass_or_display_fabricated_evidence(mutation):
    job = make_job("🎓2027届")
    requirement = rule(job, "graduation_year", "2027届", years=[2027])
    if mutation == "missing":
        requirement.evidence = []
    elif mutation == "wrong_text":
        requirement.evidence[0].text = "2026届"
    elif mutation == "wrong_field":
        requirement.evidence[0].field = "title"
    else:
        requirement.evidence[0].start = 0
        requirement.evidence[0].end = 5
    item = check(job, EligibilityProfile(graduation_year=2027), [requirement], "graduation_year")
    assert item.status == "unknown"
    assert item.evidence == []
    assert item.unknown_reason == "interpretation_uncertain"


def test_unicode_offsets_are_character_offsets_and_old_snapshot_evidence_is_rejected():
    job = make_job("🎓2027届")
    requirement = rule(job, "graduation_year", "2027届", years=[2027])
    profile = EligibilityProfile(graduation_year=2027)
    assert requirement.evidence[0].start == 1
    assert check(job, profile, [requirement], "graduation_year").status == "met"
    changed = job.model_copy(update={"description": "🎓2026届"})
    assert check(changed, profile, [requirement], "graduation_year").status == "unknown"
    assert source_fingerprint(changed) != source_fingerprint(job)


@pytest.mark.parametrize("values", [
    {"operator": "in", "min_months": 3},
    {"operator": "range", "min_months": 6, "max_months": 3},
    {"operator": "min"},
    {"operator": "min", "min_months": 3, "max_months": 6},
    {"operator": "min", "min_months": 3, "years": [2027]},
])
def test_unsupported_or_malformed_numeric_rules_are_unknown(values):
    job = make_job("时长条件")
    item = check(job, EligibilityProfile(internship_months=6),
                 [rule(job, "internship_duration", **values)], "internship_duration")
    assert item.status == "unknown"
    assert item.unknown_reason == "interpretation_uncertain"


def test_unrestricted_and_required_conditions_conflict():
    job = make_job("经验不限；至少2年经验")
    rules = [rule(job, "experience", "经验不限", kind="unrestricted", operator="any"),
             rule(job, "experience", "至少2年经验", operator="min", min_months=24)]
    item = check(job, EligibilityProfile(work_experience_months=24), rules, "experience")
    assert item.status == "unknown"
    assert item.unknown_reason == "requirements_conflict"


def test_closed_job_blocks_even_when_every_recognized_condition_passes():
    job = make_job(status="closed")
    result = evaluate_rules(job, EligibilityProfile(graduation_year=2027, degree="master", degree_status="completed",
                            acceptable_cities=[], internship_months=6), full_rules(job))
    assert all(item.status == "met" for item in result.checks)
    assert result.overall == "not_met"
    assert "关闭" in result.blocking_reasons[0]


@pytest.mark.parametrize("field,value", [
    ("title", "新标题"), ("description", "新要求"), ("city", "北京"),
    ("status", "closed"), ("source", "another"),
    ("source_url", "https://example.com/jobs/2"),
    ("updated_at", datetime(2026, 11, 12) + timedelta(hours=1)),
])
def test_fingerprint_covers_every_required_source_field(field, value):
    job = make_job()
    assert source_fingerprint(job) == source_fingerprint(job.model_copy())
    assert source_fingerprint(job) != source_fingerprint(job.model_copy(update={field: value}))


def test_invalid_rule_shape_is_unknown_even_if_constructed_without_validation():
    job = make_job()
    invalid = ConditionRule.model_construct(dimension="degree", kind="required", operator="in",
                                           degrees=["not_a_degree"], evidence=[])
    assert check(job, EligibilityProfile(degree="doctor"), [invalid], "degree").status == "unknown"


@pytest.mark.parametrize("description,state,expected", [
    ("本科及以上学历", "enrolled", "unknown"),
    ("本科及以上学历", None, "unknown"),
    ("本科及以上学历", "completed", "met"),
    ("本科在读", "enrolled", "met"),
    ("本科在读", None, "unknown"),
    ("已取得本科学历", "enrolled", "not_met"),
])
def test_actual_extraction_does_not_treat_enrollment_as_attained_degree(description, state, expected):
    job = make_job(description)
    result = evaluate_eligibility(job, EligibilityProfile(degree="bachelor", degree_status=state))
    degree = next(item for item in result.checks if item.dimension == "degree")
    assert degree.status == expected
    assert degree.evidence
    for span in degree.evidence:
        assert getattr(job, span.field)[span.start:span.end] == span.text


def test_known_degree_level_failure_remains_definite_when_attainment_unspecified():
    job = make_job("硕士在读")
    result = evaluate_eligibility(job, EligibilityProfile(degree="bachelor"))
    assert next(item for item in result.checks if item.dimension == "degree").status == "not_met"


def test_invalid_preference_citation_is_an_unverified_input_not_a_hard_rejection():
    job = make_job("本科及以上，硕士优先")
    hard = rule(job, "degree", "本科及以上", operator="min", degrees=["bachelor"])
    preference = rule(job, "degree", "硕士优先", kind="preferred", degrees=["master"])
    preference.evidence[0].field = "title"
    item = check(job, EligibilityProfile(degree="bachelor", degree_status="completed"), [hard, preference], "degree")
    assert item.status == "unknown"
    assert len(item.evidence) == 1
    assert "本科及以上" == item.evidence[0].text


@pytest.mark.parametrize("degree,expected", [("associate", "met"), ("bachelor", "met"), ("master", "not_met")])
def test_explicit_degree_upper_bound_is_supported_in_stage22(degree, expected):
    job = make_job("学历本科及以下")
    requirement = rule(job, "degree", operator="max", degrees=["bachelor"])
    item = check(job, EligibilityProfile(degree=degree, degree_status="completed"), [requirement], "degree")
    assert item.status == expected


@pytest.mark.parametrize("months,expected", [(2, "not_met"), (3, "met"), (6, "met"), (12, "unknown")])
def test_available_internship_duration_is_not_a_required_fixed_commitment(months, expected):
    job = make_job("实习3至6个月")
    requirement = rule(job, "internship_duration", operator="range", min_months=3, max_months=6)
    item = check(job, EligibilityProfile(internship_months=months), [requirement], "internship_duration")
    assert item.status == expected
    if months > 6:
        assert "能否按岗位期限安排" in item.reason
        assert item.unknown_reason == "interpretation_uncertain"
        assert "缩短" in item.next_step


def test_internship_maximum_with_longer_availability_needs_confirmation():
    job = make_job("实习最多6个月")
    requirement = rule(job, "internship_duration", operator="max", max_months=6)
    item = check(job, EligibilityProfile(internship_months=12), [requirement], "internship_duration")
    assert item.status == "unknown"
    assert item.unknown_reason == "interpretation_uncertain"


@pytest.mark.parametrize("values", [{"operator": "min"}, {"operator": "any", "min_months": 6}])
def test_invalid_unrestricted_shape_is_uncertain_not_an_invented_source_conflict(values):
    job = make_job("经验不限")
    requirement = rule(job, "experience", kind="unrestricted", **values)
    item = check(job, EligibilityProfile(), [requirement], "experience")
    assert item.status == "unknown"
    assert item.unknown_reason == "interpretation_uncertain"
    assert "不限" in item.next_step


@pytest.mark.parametrize("kind,expected", [
    ("preferred", "source_unspecified"), ("uncertain", "interpretation_uncertain"),
    ("conflict", "requirements_conflict"), ("invalid_evidence", "interpretation_uncertain"),
])
def test_source_obstacle_takes_priority_over_missing_candidate(kind, expected):
    job = make_job("要求甲；要求乙")
    if kind == "conflict":
        rules = [rule(job, "degree", "要求甲", degrees=["bachelor"]),
                 rule(job, "degree", "要求乙", degrees=["master"])]
    else:
        rules = [rule(job, "degree", "要求甲", kind=kind if kind != "invalid_evidence" else "required",
                      degrees=["bachelor"])]
        if kind == "invalid_evidence":
            rules[0].evidence = []
    item = check(job, EligibilityProfile(), rules, "degree")
    assert item.unknown_reason == expected


def test_legacy_check_defaults_do_not_guess_unknown_cause():
    item = ConditionCheck(dimension="degree", status="unknown", reason="旧说明",
                          candidate_value="未填写", requirement="旧要求", evidence=[])
    assert item.unknown_reason is None
    assert item.next_step == ""


@pytest.mark.parametrize("status", ["met", "not_met"])
def test_resolved_check_cannot_keep_stale_unknown_metadata(status):
    item = ConditionCheck(dimension="degree", status=status, reason="确定结论",
                          candidate_value="本科", requirement="本科", evidence=[],
                          unknown_reason="candidate_missing", next_step="已经不适用的提示")
    assert item.unknown_reason is None
    assert item.next_step == ""
