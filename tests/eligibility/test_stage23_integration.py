"""Public evaluator keeps the new explanations and existing hard blockers."""
from app.eligibility.contracts import EligibilityProfile
from app.eligibility.evaluator import evaluate_eligibility
from tests.eligibility.test_stage23_location import job


def test_branch_and_hybrid_are_visible_together():
    source = job('招募本科生、硕士研究生。\n本科生需有项目经历，硕士研究生有研究经验优先。\n线上线下结合。')
    result = evaluate_eligibility(source, EligibilityProfile(
        degree='master', degree_status='enrolled', acceptable_cities=['北京']))
    checks = {c.dimension: c for c in result.checks}
    assert result.rules_version == 'stage23-rules-v1'
    assert checks['degree'].status == 'met'
    assert checks['degree'].notes
    assert checks['city'].status == 'unknown'
    assert checks['city'].unknown_reason == 'interpretation_uncertain'
    assert checks['city'].next_step
    assert result.overall == 'unknown'
    for check in result.checks:
        for span in check.evidence:
            assert getattr(source, span.field)[span.start:span.end] == span.text


def test_hybrid_does_not_release_an_independent_student_block():
    result = evaluate_eligibility(job('招募本科生、硕士研究生。\n线上线下结合。'),
        EligibilityProfile(degree='master', degree_status='completed', acceptable_cities=['北京']))
    checks = {c.dimension: c for c in result.checks}
    assert checks['city'].status == 'unknown'
    assert checks['degree'].status == 'not_met'
    assert result.overall == 'not_met'


def test_remote_never_reopens_closed_job():
    source = job('支持全球全远程工作。').model_copy(update={'status': 'closed'})
    result = evaluate_eligibility(source, EligibilityProfile(acceptable_cities=['北京']))
    assert next(c for c in result.checks if c.dimension == 'city').status == 'met'
    assert result.overall == 'not_met'
    assert any('关闭' in reason for reason in result.blocking_reasons)
