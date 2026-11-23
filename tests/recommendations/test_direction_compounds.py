"""Regression and counterexamples for applicant-owned compound directions."""

from datetime import datetime
import json
from pathlib import Path

import pytest

from app.recommendations.quality import evaluate_direction
from app.schemas.job_response import JobRead
from tests.evaluation.recruitment_corpus import REQUIRES_RECORDED_CORPUS


def job(title, description):
    return JobRead(id=1, title=title, company="招聘方", city="北京", salary=None,
                   description=description, skills=[], source="manual",
                   source_url="https://careers.company.test/jobs/1", published_at=None,
                   created_at=datetime(2026, 11, 18))


def assert_directions(source, targets, expected, status=None):
    result = evaluate_direction(source, targets)
    assert set(result.detected_directions) == expected
    assert result.status == (status or ("aligned" if set(targets) & expected else
                                      "unrelated" if expected == {"other"} else "uncertain"))
    for span in result.evidence:
        assert getattr(source, span.field)[span.start:span.end] == span.text
    return result


@pytest.mark.parametrize("title,description,expected", [
    ("后端开发实习生", "工作职责：参与AI Agent应用的后端研发，包括大模型接入、工具调用、任务编排及执行结果评估。", {"backend", "ai_application"}),
    ("后端开发实习生", "工作职责：参与智能Agent及大模型应用的设计、开发与效果优化。", {"backend", "ai_application"}),
    ("Agent工程师", "工作职责：负责企业后端服务的设计、开发与维护。", {"backend", "ai_application"}),
    ("软件工程师", "你将参与：\n设计和开发视频生成及调试Agent。", {"ai_application", "computer_vision"}),
    ("后端开发实习生", "工作职责：面向视频生成与内容创作场景，参与视频模型的接入、推理部署与服务建设。", {"backend", "computer_vision", "ai_application"}),
    ("软件工程师", "岗位职责：面向图像生成应用，负责图像模型的接入与服务建设。", {"computer_vision", "ai_application"}),
    ("视觉算法工程师", "工作职责：负责后端服务的开发与维护。", {"computer_vision", "backend"}),
    ("后端开发／产品经理", "工作职责：参与Agent应用开发。", {"backend", "ai_application", "other"}),
])
def test_title_and_assigned_duties_form_a_union(title, description, expected):
    source = job(title, description)
    result = assert_directions(source, ["ai_application", "backend", "computer_vision"], expected)
    assert any(span.field == "description" for span in result.evidence)


@pytest.mark.parametrize("description", [
    "工作职责：负责CV深度学习模型和多模态大模型推理部署。",
    "工作职责：参与图像识别模型的接入和推理部署。",
    "工作职责：负责视频生成模型推理部署。",
])
def test_visual_deployment_does_not_imply_llm_application_work(description):
    source = job("软件工程师", description)
    assert_directions(source, ["ai_application"], {"computer_vision"})


@pytest.mark.parametrize("restart", ["日常实习：面向全体在校生，提供项目实践。", "ByteIntern：面向2027届毕业生。", "你将参与的工作："])
def test_actual_duties_restart_after_team_introduction(restart):
    source = job("后端开发实习生", "工作职责：\n团队介绍：参与视频模型接入，负责Agent应用开发。\n"
                 + restart + "\n1、参与AI Agent应用的后端研发。\n任职要求：熟悉Python。")
    result = assert_directions(source, ["ai_application"], {"backend", "ai_application"})
    duty_quotes = [span.text for span in result.evidence if span.field == "description"]
    assert duty_quotes == ["参与AI Agent应用的后端研发"]


@pytest.mark.parametrize("description", [
    "团队介绍：负责Agent应用开发。\n1、参与视频模型接入与推理部署。",
    "工作职责：\n团队介绍：负责Agent应用开发。\n日常实习：面向在校生。\n任职要求：参与Agent应用开发经验者优先。",
    "工作职责：\n我们是一家大模型公司，团队负责Agent应用开发，欢迎了解视觉模型的同学。",
    "工作职责：与负责Agent开发的同事协作。",
    "工作职责：参与与负责Agent开发的同事沟通。",
    "工作职责：参与Agent开发团队的需求评审。",
    "工作职责：参与Agent应用开发需求评审。",
    "工作职责：负责沟通Agent应用开发需求。",
    "工作职责：参与Agent研发项目的产品需求分析。",
    "工作职责：开发Agent培训材料。",
    "工作职责：开发Agent销售渠道。",
    "工作职责：建设Agent开发者社区。",
    "工作职责：参与Agent应用研发成果展示。",
    "工作职责：参与Agentless模块研发。",
    "工作职责：参与RAGtag模块开发。",
    "工作职责：参与面向大模型训练、推理和Agent场景的可观测平台建设。",
    "工作职责：参与面向RAG场景的日志采集平台研发。",
    "工作职责：参与Agent团队的监控平台开发。",
    "工作职责：参与大模型应用场景的可观测平台建设。",
    "工作职责：参与Agent应用的监控平台开发。",
    "工作职责：有过负责Agent开发的经验。",
    "工作职责：本岗位不参与Agent应用开发。",
    "岗位职责：负责Agent应用开发或前端页面开发。",
    "任职要求：参与Agent应用开发。",
    "加分项：负责Agent应用开发经验。",
    "工作职责：熟练使用AI工具辅助工作。",
])
def test_background_requirements_negation_and_collaboration_are_not_extra_roles(description):
    source = job("后端开发实习生", description)
    status = "unrelated" if description == "工作职责：本岗位不参与Agent应用开发。" else "uncertain"
    assert_directions(source, ["ai_application"], {"backend"}, status)


@pytest.mark.parametrize("title", ["AI产品经理", "Agent产品实习生", "公关实习生", "营销策划实习生", "品牌视觉-C端产品"])
def test_explicit_nontechnical_titles_are_not_reclassified_by_body_terms(title):
    source = job(title, "工作职责：参与Agent应用开发。负责后端服务开发。参与图像模型推理部署。")
    assert_directions(source, ["ai_application", "backend", "computer_vision"], {"other"})


def test_no_direction_evidence_remains_uncertain():
    source = job("软件工程师", "团队介绍：我们服务大模型与视频应用。\n任职要求：了解Python与OpenCV。")
    result = evaluate_direction(source, ["ai_application"])
    assert result.status == "uncertain"
    assert not result.detected_directions


def test_agent_application_work_stays_positive_when_monitoring_is_additional():
    source = job("软件工程师", "工作职责：参与Agent应用开发，并建设监控平台。")
    assert_directions(source, ["ai_application"], {"ai_application"})


def test_no_requested_targets_still_has_no_role_inference():
    result = evaluate_direction(job("后端开发实习生", "参与Agent应用开发。"), [])
    assert result.status == "not_requested"
    assert not result.detected_directions and not result.evidence


@pytest.mark.parametrize("key,targets,expected", [
    ("byte-ai-multimodal-backend", ["ai_application", "computer_vision"], {"backend", "ai_application", "computer_vision"}),
    ("byte-backend-ad", ["ai_application"], {"backend", "ai_application"}),
    ("byte-backend-commerce", ["ai_application"], {"backend", "ai_application"}),
])
@REQUIRES_RECORDED_CORPUS
def test_stage19_compound_direction_failures_are_development_regressions(key, targets, expected):
    # Stage19 is now development evidence, never the new Stage20 holdout.
    path = Path(__file__).resolve().parents[2] / "evals/cases/recommendation_quality/jobs.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    source = JobRead.model_validate(next(row["job"] for row in records if row["job_key"] == key))
    result = assert_directions(source, targets, expected)
    assert any(span.field == "description" for span in result.evidence)


@REQUIRES_RECORDED_CORPUS
def test_stage19_observability_for_agent_scenarios_is_not_ai_application_delivery():
    path = Path(__file__).resolve().parents[2] / "evals/cases/recommendation_quality/jobs.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    source = JobRead.model_validate(next(row["job"] for row in records if row["job_key"] == "minimax-backend-observability"))
    result = evaluate_direction(source, ["backend"])
    # The source is retained conservatively. Telemetry for AI workloads is not
    # enough to infer an AI application role or to exclude a backend applicant.
    assert result.status == "uncertain"
    assert not result.detected_directions
