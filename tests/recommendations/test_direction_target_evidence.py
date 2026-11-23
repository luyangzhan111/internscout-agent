"""Per-target evidence: a missing role is neither a denial nor an exclusive role."""

from datetime import datetime
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.eligibility.contracts import EvidenceSpan
from app.recommendations.quality import evaluate_direction
from app.recommendations.quality_contracts import DirectionFit, TargetDirectionCheck
from app.schemas.job_response import JobRead
from tests.evaluation.recruitment_corpus import REQUIRES_RECORDED_CORPUS


def job(title="软件工程师", description=""):
    return JobRead(id=1, title=title, description=description, company="招聘方", city="北京",
                   skills=[], source="manual", source_url="https://careers.company.test/job/1",
                   salary=None, published_at=None, created_at=datetime(2026, 11, 18))


def exact(result, source):
    for span in result.evidence:
        assert getattr(source, span.field)[span.start:span.end] == span.text
    for check in result.target_checks:
        assert all(span in result.evidence for span in check.evidence)


def statuses(result):
    return {check.target: check.status for check in result.target_checks}


def test_ai_positive_does_not_deny_an_unobserved_cv_role():
    source = job("AI应用开发工程师", "工作职责：参与Agent应用研发。")
    result = evaluate_direction(source, ["computer_vision"])
    assert result.status == "uncertain"
    assert result.detected_directions == ["ai_application"]
    assert statuses(result) == {"computer_vision": "uncertain"}
    assert not result.target_checks[0].evidence
    exact(result, source)


def test_technical_title_is_not_a_negative_for_other_targets():
    source = job("计算机视觉工程师")
    result = evaluate_direction(source, ["ai_application", "backend"])
    assert result.status == "uncertain"
    assert result.detected_directions == ["computer_vision"]
    assert statuses(result) == {"ai_application": "uncertain", "backend": "uncertain"}


def test_requested_target_order_and_deduplication_are_preserved():
    source = job("AI应用开发工程师")
    result = evaluate_direction(source, ["computer_vision", "ai_application", "computer_vision"])
    assert [check.target for check in result.target_checks] == ["computer_vision", "ai_application"]
    assert [check.status for check in result.target_checks] == ["uncertain", "aligned"]
    assert result.status == "aligned"


def test_one_denied_target_and_one_unknown_target_remain_uncertain():
    source = job(description="工作职责：本岗位不负责后端开发。")
    result = evaluate_direction(source, ["backend", "computer_vision"])
    assert result.status == "uncertain"
    assert statuses(result) == {"backend": "unrelated", "computer_vision": "uncertain"}
    exact(result, source)


def test_only_all_explicitly_denied_targets_are_unrelated():
    source = job(description="工作职责：本岗位不负责后端开发。该岗位不涉及计算机视觉工作。")
    result = evaluate_direction(source, ["backend", "computer_vision"])
    assert result.status == "unrelated"
    assert not result.detected_directions
    assert statuses(result) == {"backend": "unrelated", "computer_vision": "unrelated"}
    exact(result, source)


@pytest.mark.parametrize("title,description", [
    ("后端开发工程师", "工作职责：本岗位不负责后端开发。"),
    ("软件工程师", "工作职责：负责后端服务开发。本岗位不负责后端开发。"),
    ("软件工程师", "工作职责：负责后端服务开发，但不负责后端开发。"),
    ("软件工程师", "工作职责：不负责后端开发，但负责后端服务研发。"),
])
def test_positive_and_negative_evidence_for_the_same_target_stay_uncertain(title, description):
    source = job(title, description)
    result = evaluate_direction(source, ["backend"])
    assert result.status == "uncertain"
    assert "backend" in result.detected_directions
    assert statuses(result) == {"backend": "uncertain"}
    assert len(result.target_checks[0].evidence) >= 2
    exact(result, source)


def test_one_positive_target_wins_global_aggregation_over_another_negative():
    source = job("AI应用开发工程师", "工作职责：不负责后端开发。")
    result = evaluate_direction(source, ["backend", "ai_application"])
    assert result.status == "aligned"
    assert statuses(result) == {"backend": "unrelated", "ai_application": "aligned"}


@pytest.mark.parametrize("title", ["产品经理", "Agent产品实习生", "公关实习生", "营销策划实习生", "品牌视觉-C端产品"])
def test_protected_nontechnical_titles_deny_all_requested_technical_targets(title):
    source = job(title, "工作职责：参与Agent应用开发。负责后端服务开发。")
    result = evaluate_direction(source, ["ai_application", "backend", "computer_vision"])
    assert result.status == "unrelated"
    assert result.detected_directions == ["other"]
    assert all(check.status == "unrelated" for check in result.target_checks)
    exact(result, source)


def test_explicit_dual_title_is_not_protected_as_pure_product_work():
    source = job("后端开发／产品经理")
    result = evaluate_direction(source, ["ai_application", "backend"])
    assert result.status == "aligned"
    assert statuses(result) == {"ai_application": "uncertain", "backend": "aligned"}


@pytest.mark.parametrize("title,detected", [
    ("软件工程师（非产品经理）", set()),
    ("软件工程师／非产品经理", set()),
    ("后端开发／非产品经理", {"backend"}),
])
def test_negated_nontechnical_role_is_not_a_protected_positive_title(title, detected):
    result = evaluate_direction(job(title), ["ai_application"])
    assert result.status == "uncertain"
    assert set(result.detected_directions) == detected


def test_positive_role_survives_a_separately_negated_title_component():
    result = evaluate_direction(job("AI应用开发／非后端开发岗位"), ["ai_application", "backend"])
    assert result.status == "aligned"
    assert statuses(result) == {"ai_application": "aligned", "backend": "unrelated"}
    assert result.detected_directions == ["ai_application"]


@pytest.mark.parametrize("description", [
    "工作职责：与不负责后端开发的同事协作。",
    "团队介绍：本团队不负责后端开发。",
    "任职要求：无需后端开发经验。",
    "任职要求：本岗位不负责后端开发。",
    "加分项：非后端开发经验者优先。",
    "工作职责：曾经不负责后端开发。",
    "工作职责：本岗不一定负责后端开发。",
    "工作职责：本岗不负责后端开发培训。",
    "工作职责：本岗不负责后端开发经验审核。",
    "工作职责：本岗不负责招聘后端工程师。",
    "工作职责：熟悉AI工具即可，无需计算机视觉经验。",
])
def test_non_role_negation_never_becomes_a_hard_direction_denial(description):
    result = evaluate_direction(job(description=description), ["backend", "computer_vision"])
    assert result.status == "uncertain"
    assert all(check.status == "uncertain" for check in result.target_checks)


@pytest.mark.parametrize("target,role", [
    ("ai_application", "开发大模型应用"), ("backend", "后端开发"),
    ("computer_vision", "CV算法研发"), ("data", "数据开发"),
    ("frontend", "前端开发"), ("test_development", "测试开发"),
    ("devops", "DevOps工作"), ("security", "安全研发"),
])
def test_explicit_applicant_denials_cover_each_supported_target(target, role):
    source = job(description="工作职责：本岗位不负责" + role + "。")
    result = evaluate_direction(source, [target])
    assert result.status == "unrelated"
    assert statuses(result) == {target: "unrelated"}
    exact(result, source)


@pytest.mark.parametrize("description,expected", [
    ("工作职责：参与基于大模型的多模态Agent研发，围绕图像生成、图文理解等场景，优化Agent任务规划和结果评估。", "aligned"),
    ("工作职责：参与图文理解Agent研发。", "aligned"),
    ("工作职责：参与多模态Agent研发，面向语音交互优化任务规划。", "uncertain"),
    ("工作职责：参与多模态Agent研发。任职要求：熟悉图文理解。", "uncertain"),
    ("工作职责：参与Agent应用研发。团队介绍：负责图像生成Agent开发。", "uncertain"),
    ("工作职责：与负责图文理解Agent研发的同事协作。", "uncertain"),
])
def test_visual_agent_delivery_has_positive_cv_evidence_but_multimodal_alone_does_not(description, expected):
    source = job(description=description)
    result = evaluate_direction(source, ["computer_vision"])
    assert result.status == expected
    exact(result, source)


@REQUIRES_RECORDED_CORPUS
def test_stage20_visual_agent_false_exclusion_is_a_development_regression():
    path = Path(__file__).resolve().parents[2] / "evals/cases/recommendation_quality_stage20/jobs.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    source = JobRead.model_validate(next(row["job"] for row in rows if row["job_key"] == "sensetime-ai-agent-intern"))
    result = evaluate_direction(source, ["computer_vision"])
    assert result.status == "aligned"
    assert {"ai_application", "computer_vision"} <= set(result.detected_directions)
    exact(result, source)


@REQUIRES_RECORDED_CORPUS
def test_stage20_scientific_agent_does_not_deny_unrecognized_backend_delivery():
    path = Path(__file__).resolve().parents[2] / "evals/cases/recommendation_quality_stage20/jobs.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    source = JobRead.model_validate(next(row["job"] for row in rows if row["job_key"] == "dp-ai-scientific-agent"))
    result = evaluate_direction(source, ["backend"])
    assert result.status == "uncertain"
    assert "ai_application" in result.detected_directions
    exact(result, source)


def quote(text="Agent研发"):
    return EvidenceSpan(field="description", text=text, start=0, end=len(text))


def test_new_contract_can_preserve_other_positive_clues_for_an_unknown_target():
    q = quote()
    fit = DirectionFit(status="uncertain", detected_directions=["ai_application"], reason="视觉方向未确认",
                       evidence=[q], target_checks=[TargetDirectionCheck(target="computer_vision", status="uncertain", reason="缺少视觉证据")])
    assert fit.target_checks[0].status == "uncertain"
    with pytest.raises(ValidationError):
        DirectionFit(status="uncertain", detected_directions=["ai_application"], reason="旧协议不允许", evidence=[q])


@pytest.mark.parametrize("invalid", [
    {"status": "aligned", "detected_directions": ["ai_application"], "target_checks": [{"target": "computer_vision", "status": "uncertain", "reason": "待确认"}]},
    {"status": "unrelated", "target_checks": [{"target": "backend", "status": "unrelated", "reason": "否定", "evidence": [quote()]}, {"target": "backend", "status": "unrelated", "reason": "重复", "evidence": [quote()]}]},
    {"status": "aligned", "detected_directions": ["ai_application"], "target_checks": [{"target": "backend", "status": "aligned", "reason": "错误角色", "evidence": [quote()]}]},
    {"status": "unrelated", "detected_directions": ["backend"], "target_checks": [{"target": "backend", "status": "unrelated", "reason": "冲突不能确定", "evidence": [quote()]}]},
    {"status": "unrelated", "target_checks": [{"target": "backend", "status": "unrelated", "reason": "无证据"}]},
    {"status": "not_requested", "target_checks": [{"target": "backend", "status": "uncertain", "reason": "不应有检查"}]},
])
def test_contract_rejects_inconsistent_per_target_decisions(invalid):
    with pytest.raises(ValidationError):
        DirectionFit(reason="测试", evidence=[quote()], **invalid)


def test_target_quote_must_be_present_in_source_bound_parent_evidence():
    q = quote()
    with pytest.raises(ValidationError):
        DirectionFit(status="unrelated", reason="否定", evidence=[],
                     target_checks=[TargetDirectionCheck(target="backend", status="unrelated", reason="否定", evidence=[q])])


def test_no_requested_targets_has_no_checks_or_role_claims():
    result = evaluate_direction(job("AI应用工程师", "参与Agent应用开发。"), [])
    assert result.status == "not_requested"
    assert not result.target_checks and not result.evidence and not result.detected_directions
