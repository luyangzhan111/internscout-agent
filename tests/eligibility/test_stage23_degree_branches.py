"""Development examples for applicant degree scope; no Stage23 holdout is read."""

import json
from pathlib import Path

import pytest

from app.eligibility.contracts import ConditionRule, EligibilityProfile
from app.eligibility.evaluator import evaluate_eligibility
from app.eligibility.extractor import extract_conditions
from app.schemas.job_response import JobRead
from tests.eligibility.test_stage22_degree_review import source_job, degree
from tests.evaluation.recruitment_corpus import REQUIRES_RECORDED_CORPUS


@pytest.mark.parametrize("ability", [
    "本科生具备课程项目、算法竞赛、论文复现等经历即可；硕士研究生具备相关研究经历者优先。",
    "本科生具备良好的学习能力和实验执行能力；硕士研究生能够较独立运行训练与评测任务。",
    "本科生重点考察编程基础、学习能力以及研究兴趣；硕士研究生希望具备一定科研项目经验。",
    "本科生要求：具备基础编程能力和较强学习能力；硕士研究生要求：具备一定数据分析或科研项目经验。",
])
@pytest.mark.parametrize("candidate", ["bachelor", "master"])
def test_degree_labelled_capabilities_do_not_narrow_the_shared_applicant_list(ability, candidate):
    text = "招募对象：本科生、硕士研究生。" + ability
    check = degree(text, candidate, "enrolled")
    assert check.status == "met"
    assert any("分学历能力说明" in note and "仍需核对" in note for note in check.notes)
    rules = extract_conditions(source_job(text))
    branches = [rule for rule in rules if rule.degree_scope == "conditional_capability"]
    assert branches and all(rule.dimension == "degree" for rule in branches)
    assert any(rule.kind == "required" and rule.degrees == ["bachelor", "master"]
               for rule in rules if rule.degree_scope == "applicant")
    assert degree(text, candidate, "completed").status == "not_met"


@pytest.mark.parametrize("text", [
    "招募对象：本科生、硕士研究生。", "本科生、硕士研究生。",
    "任职要求：\n1. 本科生、硕士研究生。", "招募对象本科生、硕士研究生。",
    "仅面向本科生和硕士研究生。",
])
def test_explicit_student_applicants_require_enrollment(text):
    assert degree(text, "master", "enrolled").status == "met"
    assert degree(text, "master", "completed").status == "not_met"
    assert degree(text, "bachelor", None).unknown_reason == "candidate_missing"


def test_ability_branch_cannot_hide_a_real_degree_certificate_state():
    text = "招募对象：本科生、硕士研究生。本科生有项目经历并持有学士证书。"
    check = degree(text, "bachelor", "enrolled")
    assert check.status == "unknown"
    assert check.unknown_reason == "requirements_conflict"


@pytest.mark.parametrize("text", [
    "本科生具备项目经历。", "硕士研究生能够运行训练任务。",
    "本科生要求：具备一定编程能力。", "研究生背景优先。",
    "本科生、硕士研究生优先。", "团队招收本科生与硕士研究生。",
    "与硕士研究生团队共同研发。", "硕士研究生导师同意。",
    "面向本科生的咨询服务平台。", "学历背景：本科生、硕士研究生。",
])
def test_capabilities_preferences_and_non_applicant_scope_do_not_infer_enrollment(text):
    result = degree(text, "master", "completed")
    assert result.status != "not_met"
    assert not any(rule.degree_status == "enrolled" and rule.kind == "required"
                   for rule in extract_conditions(source_job(text)))


@pytest.mark.parametrize("text", [
    "本科生须已毕业；硕士生须在读。",
    "本科生要求：已取得学位且具备编程能力；硕士研究生要求：在读。",
    "本科生具备项目经验或3年正式工作经验。",
    "本科已取得或硕士在读。", "2027届本科在读或2026届硕士已毕业。",
    "招募对象：本科已取得或硕士在读。",
])
@pytest.mark.parametrize("candidate,state", [("bachelor", "completed"), ("master", "enrolled")])
def test_status_branches_and_correlated_alternatives_are_not_discarded_as_capabilities(text, candidate, state):
    assert degree(text, candidate, state).status == "unknown"
    assert not any(rule.degree_scope == "conditional_capability"
                   for rule in extract_conditions(source_job(text)) if rule.dimension == "degree")


@pytest.mark.parametrize("text", ["硕士研究生在读。", "学历要求：硕士。", "招募对象：本科生、硕士研究生。"])
def test_unstated_acceptance_of_higher_degree_remains_unknown(text):
    check = degree(text, "doctor", "enrolled" if "生" in text else "completed")
    assert check.status == "unknown" and check.unknown_reason == "interpretation_uncertain"
    assert "更高学历" in check.next_step


@pytest.mark.parametrize("text", ["硕士研究生在读。", "在校生；学历要求：硕士。", "招募对象：本科生、硕士研究生。"])
def test_higher_degree_uncertainty_does_not_hide_known_independent_state_failure(text):
    check = degree(text, "doctor", "completed")
    assert check.status == "not_met" and "状态" in check.reason


@pytest.mark.parametrize("text", ["仅限硕士研究生在读。", "只接受硕士学历。", "硕士及以下学历。"])
def test_explicit_exclusive_degree_or_upper_bound_still_rejects_higher_level(text):
    assert degree(text, "doctor", "enrolled" if "在读" in text else "completed").status == "not_met"


def test_scope_metadata_is_optional_for_old_saved_rules_and_restricted_to_degree():
    old = ConditionRule(dimension="degree", kind="required", operator="in", degrees=["master"])
    assert old.degree_scope == "applicant" and not old.degree_exclusive
    with pytest.raises(ValueError):
        ConditionRule(dimension="experience", kind="required", operator="unknown", degree_scope="conditional_capability")
    with pytest.raises(ValueError):
        ConditionRule(dimension="degree", kind="required", operator="unknown", degree_scope="conditional_capability", degree_status="enrolled")


@REQUIRES_RECORDED_CORPUS
def test_stage22_known_degree_errors_are_replayed_as_development_evidence():
    root = Path(__file__).resolve().parents[2] / "evals/cases/recommendation_quality_stage22"
    jobs = {row["job_key"]: JobRead.model_validate(row["job"]) for row in (
        json.loads(line) for line in (root / "jobs.jsonl").read_text(encoding="utf-8").splitlines())}
    profiles = {row["profile_id"]: EligibilityProfile.model_validate(row["candidate"]["conditions"])
                for row in json.loads((root / "profiles.json").read_text(encoding="utf-8"))["profiles"]}
    gold = [json.loads(line) for line in (root / "gold.jsonl").read_text(encoding="utf-8").splitlines()]
    false_blocks, recall = [], []
    for row in gold:
        result = evaluate_eligibility(jobs[row["job_key"]], profiles[row["profile_id"]])
        check = next(check for check in result.checks if check.dimension == "degree")
        if row["eligibility"]["degree"] != "not_met" and check.status == "not_met":
            false_blocks.append((row["job_key"], row["profile_id"]))
        if row["eligibility"]["degree"] == "not_met" and check.status == "not_met":
            recall.append((row["job_key"], row["profile_id"]))
        if row["job_key"] == "sii-cv-video-diffusion" and row["profile_id"] in {
            "ai-masters-campus", "cv-masters-campus", "multimodal-ai-cv-campus",
        }:
            assert check.status == "met"
            assert result.overall != "not_met"
    assert false_blocks == []
    assert len(recall) == 75
