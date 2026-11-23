"""Ordering support is source-bound and leaves classification/retention alone."""

import ast
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from pydantic import ValidationError

from app.eligibility.contracts import EvidenceSpan
from app.eligibility.evaluator import evaluate_eligibility
from app.matching.contracts import CandidateProfile
from app.matching.matcher import CandidateMatcher
from app.matching.skill_extractor import JobSkillExtractor
from app.recommendations.contracts import RecommendationCandidate
from app.recommendations.quality import (
    classify_skill_requirements, evaluate_direction, evaluate_ranking_support, quality_rank_key,
)
from app.recommendations.quality_contracts import RankingSupport
from app.schemas.job_response import JobRead
from tests.evaluation.recruitment_corpus import REQUIRES_RECORDED_CORPUS
from tests.recommendations.test_quality import row

ROOT = Path(__file__).resolve().parents[2]


def job(title="软件实习工程师", description="", **changes):
    return JobRead(id=1, title=title, description=description, company="招聘方", city="北京", skills=[],
                   source="manual", source_url="https://careers.fixture.test/jobs/1", salary=None,
                   published_at=None, created_at=datetime(2026, 11, 18), **changes)


def support(source, targets=("computer_vision",), skills=("OpenCV", "Python")):
    fit = evaluate_direction(source, targets)
    before = fit.model_dump()
    result = evaluate_ranking_support(source, targets, fit, skills)
    assert fit.model_dump() == before
    for span in result.evidence:
        assert getattr(source, span.field)[span.start:span.end] == span.text
    return fit, result


@pytest.mark.parametrize("description", [
    "任职要求：熟练掌握Python、SQL、PyTorch、Docker和Linux。",
    "岗位职责：负责Python和PyTorch模块开发。",
    "使用AI工具和Python处理工作材料。",
])
def test_shared_technical_skills_alone_do_not_promote_a_target(description):
    fit, result = support(job(description=description), skills=["Python", "SQL", "PyTorch", "Docker", "Linux"])
    assert fit.status == "uncertain"
    assert result.level == "insufficient"
    assert result.targets == result.matched_target_skills == []


@pytest.mark.parametrize("target,skill,description", [
    ("computer_vision", "OpenCV", "任职要求：熟悉OpenCV。"),
    ("backend", "FastAPI", "任职要求：熟悉FastAPI框架。"),
    ("ai_application", "RAG", "任职要求：熟悉RAG技术。"),
    ("frontend", "HTML", "任职要求：掌握HTML。"),
    ("ai_application", "LLM", "任职要求：熟悉LLM应用评测。"),
])
def test_required_specialized_intersections_promote_only_order_not_direction(target, skill, description):
    fit, result = support(job(description=description), [target], [skill, "Python"])
    assert fit.status == "uncertain"
    assert result.level == "target_specific"
    assert result.targets == [target] and result.matched_target_skills == [skill]
    assert result.evidence and "待确认" in result.reason


def test_unmatched_specialized_requirement_does_not_invent_a_candidate_skill():
    fit, result = support(job(description="任职要求：熟悉OpenCV。"), skills=["Python"])
    assert fit.status == "uncertain" and result.level == "insufficient"
    assert not result.matched_target_skills


@pytest.mark.parametrize("title,description", [
    ("大模型算法研发实习生", "任职要求：熟悉LLM与PyTorch。"),
    ("基座大模型研究工程师", "工作职责：负责大模型预训练算法研究。"),
    ("软件工程师", "工作职责：使用RAG平台设计市场宣传材料。"),
    ("软件工程师", "工作职责：借助大模型开发营销文案模板。"),
    ("软件工程师", "任职要求：熟悉RAG平台的使用。"),
])
def test_foundation_model_research_and_general_model_tool_usage_are_not_application_support(title, description):
    _, result = support(job(title, description), ["ai_application"], ["LLM", "RAG", "PyTorch"])
    assert result.level == "insufficient"


@pytest.mark.parametrize("title,description", [
    ("软件工程师", "加分项：熟悉OpenCV优先。"),
    ("软件工程师", "岗位职责：与负责OpenCV图像模型研发的同事协作。"),
    ("软件工程师", "团队介绍：负责图像模型训练。"),
    ("软件工程师", "岗位职责：团队负责图像模型研发。"),
    ("软件工程师", "岗位职责：我们的团队研发图像模型。"),
    ("软件工程师", "岗位职责：本部门构建图像模型。"),
    ("软件工程师", "曾参与OpenCV图像模型研发。"),
    ("软件工程师", "岗位职责：利用AI工具生成图像模型报告。"),
    ("软件工程师", "任职要求：熟悉OpenCV工具使用。"),
    ("算法实习生（OpenCV背景优先）", ""),
])
def test_preferences_collaborators_history_and_ai_tool_usage_are_not_promoted(title, description):
    _, result = support(job(title, description))
    assert result.level == "insufficient"


@pytest.mark.parametrize("description", [
    "任职要求：不要求OpenCV经验。", "任职要求：不熟悉OpenCV也可。",
    "任职要求：不强制要求OpenCV。", "任职要求：没有OpenCV经验也可以。",
])
def test_waived_or_negated_specialized_requirements_do_not_promote_order(description):
    _, result = support(job(description=description))
    assert result.level == "insufficient"


@pytest.mark.parametrize("target,description", [
    ("computer_vision", "岗位职责：负责整理图像模型训练相关材料。"),
    ("computer_vision", "岗位职责：协助算法工程师完成图像模型研发相关文档的整理。"),
    ("ai_application", "岗位职责：负责整理RAG系统开发相关宣传材料。"),
    ("backend", "岗位职责：协助后端工程师整理API接口系统设计文档。"),
    ("computer_vision", "岗位职责：负责图像模型研发文档的整理。"),
    ("ai_application", "任职要求：有RAG系统开发相关宣传材料的编写能力。"),
])
def test_technical_work_named_in_documentation_is_not_a_role_assignment(target, description):
    fit, result = support(job(description=description), [target], ["RAG", "OpenCV", "FastAPI"])
    assert fit.status == "uncertain" and result.level == "insufficient"


def test_actual_training_before_record_keeping_retains_ordering_support():
    fit, result = support(job(description="岗位职责：负责图像深度模型的训练与量化，并整理实验记录。"),
                          ["computer_vision"], [])
    assert fit.status == "uncertain" and result.level == "target_specific"


@pytest.mark.parametrize("target,title,description", [
    ("computer_vision", "算法工程师（视觉多模态方向）", ""),
    ("backend", "软件工程师", "工作职责：负责API接口系统的设计。"),
    ("ai_application", "软件工程师", "工作职责：智能体任务规划模块设计。"),
    ("computer_vision", "软件工程师", "工作职责：参与图像深度模型的训练与量化。"),
    ("data", "软件工程师", "工作职责：负责数据管道的优化。"),
    ("frontend", "软件工程师", "工作职责：负责网页交互页面的设计和实现。"),
    ("test_development", "软件工程师", "工作职责：负责测试用例生成工具的优化。"),
    ("devops", "软件工程师", "工作职责：参与持续部署流水线的优化。"),
    ("security", "软件工程师", "工作职责：参与漏洞挖掘工具的优化。"),
])
def test_assigned_technical_topic_can_support_inspection_without_resolving_direction(target, title, description):
    fit, result = support(job(title, description), [target], [])
    assert fit.status == "uncertain"
    assert result.level == "target_specific" and result.targets == [target]
    assert result.matched_target_skills == []


def test_known_other_direction_is_demoted_but_stays_uncertain():
    fit, result = support(job("后端开发工程师", "任职要求：熟悉Python。"))
    assert fit.status == "uncertain" and fit.detected_directions == ["backend"]
    assert result.level == "other_direction" and result.evidence[0].field == "title"
    assert result.targets == result.matched_target_skills == []


def test_target_specific_delivery_can_outweigh_other_direction_clues():
    fit, result = support(job("后端开发工程师", "工作职责：参与图像深度模型的训练与量化。"))
    assert fit.status == "uncertain" and "backend" in fit.detected_directions
    assert result.level == "target_specific" and result.targets == ["computer_vision"]


def test_multitarget_support_preserves_request_order_without_inventing_other_target_support():
    _, result = support(job(description="任职要求：熟悉RAG、OpenCV和Python。"),
                        ["computer_vision", "backend", "ai_application"], ["Python", "RAG", "OpenCV"])
    assert result.targets == ["computer_vision", "ai_application"]
    assert result.matched_target_skills == ["RAG", "OpenCV"]


def test_conflicting_or_explicitly_denied_target_is_not_rewarded():
    source = job("后端开发工程师", "工作职责：本岗位不负责后端开发。")
    fit, result = support(source, ["backend"])
    assert fit.status == "uncertain" and result.level == "insufficient"
    source = job(description="本岗位不负责后端开发。任职要求：熟悉FastAPI。")
    fit, result = support(source, ["backend", "computer_vision"], ["FastAPI"])
    assert fit.status == "uncertain" and result.level == "insufficient"


@pytest.mark.parametrize("title,targets", [("后端开发工程师", ["backend"]),
                                           ("公关经理", ["backend"]), ("软件工程师", [])])
def test_non_uncertain_direction_groups_keep_their_existing_order(title, targets):
    fit, result = support(job(title), targets)
    assert fit.status != "uncertain" and result.level == "not_applicable"
    assert not result.targets and not result.evidence and not result.matched_target_skills


def test_support_rank_is_inside_qualification_and_direction_groups_before_shared_skill_coverage():
    def ranked(identifier, level, **kwargs):
        item = row(identifier, **kwargs)
        item.ranking_support = SimpleNamespace(level=level)
        return item
    items = [ranked(1, "other_direction", eligibility="met", direction="uncertain", score=1),
             ranked(2, "not_applicable", direction="aligned", score=1),
             ranked(3, "target_specific", direction="uncertain", score=1),
             ranked(4, "insufficient", direction="uncertain", score=99),
             ranked(5, "other_direction", direction="uncertain", score=100)]
    assert [item.job.id for item in sorted(reversed(items), key=quality_rank_key)] == [1, 2, 3, 4, 5]
    assert [item.job.id for item in items] == [1, 2, 3, 4, 5]  # no filtering/mutation
    assert len(quality_rank_key(row(1))) == 7


@pytest.mark.parametrize("invalid", [
    {"level": "target_specific", "targets": []},
    {"level": "target_specific", "targets": ["backend"]},
    {"level": "other_direction"},
    {"level": "insufficient", "targets": ["backend"]},
    {"level": "insufficient", "matched_target_skills": ["FastAPI"]},
    {"level": "not_applicable", "evidence": [EvidenceSpan(field="title", text="标题", start=0, end=2)]},
    {"level": "insufficient", "reason": " "},
    {"level": "other_direction", "evidence": [EvidenceSpan(field="city", text="北京", start=0, end=2)]},
    {"level": "target_specific", "targets": ["backend", "backend"],
     "evidence": [EvidenceSpan(field="title", text="后端", start=0, end=2)]},
])
def test_support_model_rejects_contradictory_metadata(invalid):
    with pytest.raises(ValidationError):
        RankingSupport.model_validate({"reason": "判断依据", **invalid})


def test_old_direction_and_skill_parser_asts_are_unchanged_from_degree_only_archive():
    with ZipFile(ROOT / "evals/baselines/stage22_degree_only/application.zip") as archive:
        old = ast.parse(archive.read("app/recommendations/quality.py").decode("utf-8"))
    new = ast.parse((ROOT / "app/recommendations/quality.py").read_text(encoding="utf-8"))
    old_functions = {node.name: ast.dump(node, include_attributes=False) for node in old.body
                     if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name != "quality_rank_key"}
    new_functions = {node.name: ast.dump(node, include_attributes=False) for node in new.body
                     if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    assert all(new_functions[name] == tree for name, tree in old_functions.items())


@REQUIRES_RECORDED_CORPUS
def test_all_three_old_development_corpora_reduce_wrong_direction_without_losing_relevant_top_five():
    """Development guard only; these80 old jobs are not a new holdout."""
    total = {"before_relevant": 0, "after_relevant": 0, "before_wrong_direction": 0, "after_wrong_direction": 0}
    matcher, extractor = CandidateMatcher(), JobSkillExtractor()
    for corpus in ("recommendation_quality", "recommendation_quality_stage20", "recommendation_quality_stage21_holdout26"):
        directory = ROOT / "evals/cases" / corpus
        frozen = json.loads((directory / "dataset_freeze.json").read_text(encoding="utf-8"))["files"]
        for name in ("jobs.jsonl", "profiles.json", "gold.jsonl"):
            assert sha256((directory / name).read_bytes()).hexdigest() == frozen[name]
        records = [json.loads(line) for line in (directory / "jobs.jsonl").read_text(encoding="utf-8").splitlines()]
        profiles = json.loads((directory / "profiles.json").read_text(encoding="utf-8"))["profiles"]
        labels = [json.loads(line) for line in (directory / "gold.jsonl").read_text(encoding="utf-8").splitlines()]
        gold = {(r["profile_id"], r["job_key"]): r for r in labels}
        for profile in profiles:
            candidate = RecommendationCandidate.model_validate(profile["candidate"])
            before, after = [], []
            for record in records:
                source = JobRead.model_validate(record["job"])
                eligibility = evaluate_eligibility(source, candidate.conditions)
                fit = evaluate_direction(source, candidate.target_directions)
                if source.status == "closed" or eligibility.overall == "not_met" or fit.status == "unrelated":
                    continue
                match = matcher.match(candidate=CandidateProfile(skills=candidate.skills), job=source,
                                      evidence=extractor.extract(source))
                values = {**match.model_dump(), "job": source, "eligibility": eligibility, "direction_fit": fit,
                          "skill_requirements": classify_skill_requirements(source, match.detected_job_skills, candidate.skills),
                          "job_key": record["job_key"]}
                before.append(SimpleNamespace(**values))
                after.append(SimpleNamespace(**values, ranking_support=evaluate_ranking_support(
                    source, candidate.target_directions, fit, match.matched_skills)))
            before.sort(key=quality_rank_key)
            after.sort(key=quality_rank_key)
            assert {row.job_key for row in before} == {row.job_key for row in after}
            for name, ranked in (("before", before), ("after", after)):
                judged = [gold[(profile["profile_id"], row.job_key)] for row in ranked[:5]]
                total[name + "_relevant"] += sum(item["relevance"] >= 2 for item in judged)
                total[name + "_wrong_direction"] += sum(item["direction"] == "unrelated" for item in judged)
    print(total)
    assert total["after_wrong_direction"] < total["before_wrong_direction"], total
    assert total["after_relevant"] >= total["before_relevant"], total
