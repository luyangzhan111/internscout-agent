"""Graduate ranges are alternatives, with only the stated common study status."""
import json
from pathlib import Path

import pytest

from app.eligibility.contracts import EligibilityProfile
from app.eligibility.evaluator import evaluate_eligibility
from app.schemas.job_response import JobRead
from tests.eligibility.test_stage20_degree import degree_check
from tests.evaluation.recruitment_corpus import REQUIRES_RECORDED_CORPUS


@pytest.mark.parametrize("text", [
    "在读本科生或研究生。", "本科生或研究生在读。", "本科生，研究生在读。",
    "本科生、研究生在读。", "本科/研究生在读。",
])
@pytest.mark.parametrize("degree", ["bachelor", "master", "doctor"])
def test_undergraduate_or_postgraduate_list_keeps_every_permitted_branch(text, degree):
    assert degree_check(text, degree=degree, degree_status="enrolled").status == "met"
    assert degree_check(text, degree=degree, degree_status="completed").status == "not_met"


@pytest.mark.parametrize("text", [
    "研究生/博士生在读。", "研究生、博士生在读。", "研究生，博士生在读。",
    "硕博在读。", "在读硕博。", "硕士或博士在读。", "研究生学历在读。",
])
@pytest.mark.parametrize("degree,expected", [("bachelor", "not_met"), ("master", "met"), ("doctor", "met")])
def test_postgraduate_group_is_not_narrowed_to_the_last_or_highest_degree(text, degree, expected):
    assert degree_check(text, degree=degree, degree_status="enrolled").status == expected


@pytest.mark.parametrize("text", ["硕士研究生在读。", "博士研究生在读。"])
def test_named_postgraduate_degree_does_not_expand_into_a_different_degree(text):
    accepted = "master" if text.startswith("硕士") else "doctor"
    rejected = "doctor" if accepted == "master" else "master"
    assert degree_check(text, degree=accepted, degree_status="enrolled").status == "met"
    assert degree_check(text, degree=rejected, degree_status="enrolled").status == ("unknown" if rejected == "doctor" else "not_met")


@pytest.mark.parametrize("text", [
    "硕士在读或博士。", "已取得硕士或博士在读。", "研究生或社会人士。",
    "研究生/博士生在读或3年工作经验。", "硕博连读。", "研究生专业说明需确认。",
    "硕士及以上学历。研究生在读/社会人士。",
])
def test_unresolved_identity_and_study_scope_cannot_create_a_hard_gate(text):
    assert degree_check(text, degree="bachelor", degree_status="completed").status == "unknown"


@pytest.mark.parametrize("text", ["研究生在读优先。", "研究生导师同意。", "与研究生协作研发。", "不接受研究生。"])
def test_preferences_negation_and_other_people_are_not_new_hard_requirements(text):
    assert degree_check(text, degree="bachelor", degree_status="completed").status == "unknown"


def test_unknown_candidate_status_and_unstated_acceptance_remain_unknown():
    assert degree_check("研究生/博士生在读。", degree="master").status == "unknown"
    assert degree_check("研究生学历。", degree="master", degree_status="enrolled").status == "unknown"
    assert degree_check("研究生学历。", degree="doctor", degree_status="completed").status == "met"


@REQUIRES_RECORDED_CORPUS
def test_the_four_stage21_false_degree_blocks_are_development_regressions():
    root = Path(__file__).resolve().parents[2] / "evals/cases/recommendation_quality_stage21_holdout26"
    jobs = {row["job_key"]: JobRead.model_validate(row["job"]) for row in (
        json.loads(line) for line in (root / "jobs.jsonl").read_text(encoding="utf-8").splitlines())}
    profiles = {row["profile_id"]: row["candidate"] for row in json.loads((root / "profiles.json").read_text(encoding="utf-8"))["profiles"]}
    for key, profile in [
        ("momenta-ai-tools", "ai-masters-campus"), ("momenta-ai-tools", "multimodal-ai-cv-campus"),
        ("mammotion-cv-stereo-depth", "cv-masters-campus"), ("mammotion-cv-stereo-depth", "multimodal-ai-cv-campus"),
    ]:
        result = evaluate_eligibility(jobs[key], EligibilityProfile.model_validate(profiles[profile]["conditions"]))
        assert next(check.status for check in result.checks if check.dimension == "degree") == "met"
        assert result.overall != "not_met"
