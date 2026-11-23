"""Manually labelled development examples for conservative, source-bound rules."""

from datetime import datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.recommendations.quality import classify_skill_requirements, evaluate_direction, quality_rank_key
from app.recommendations.quality_contracts import DirectionFit, SkillRequirement
from app.schemas.job_response import JobRead


def job(title="开发实习生", description=""):
    return JobRead(id=1, title=title, company="招聘方", description=description, city="深圳",
                   skills=[], source="manual", source_url="https://jobs.company.cn/jobs/1",
                   salary=None, published_at=None, created_at=datetime(2026, 11, 17))


def exact(item, source):
    for span in item.evidence:
        assert getattr(source, span.field)[span.start:span.end] == span.text


# Status labels were assigned from the role and duties, independently of ranking or skills.
ROLE_CASES = [
    ("公关实习生", "任职要求：熟练使用 Python；熟悉 AI 应用。", ["ai_application"], "unrelated", {"other"}),
    ("营销策划实习生", "负责开发大模型应用，推广 AI 产品。", ["ai_application"], "unrelated", {"other"}),
    ("AI 产品经理", "熟悉大模型、Agent、RAG。", ["ai_application"], "unrelated", {"other"}),
    ("项目管理实习生", "参与前端开发。", ["frontend"], "unrelated", {"other"}),
    ("生物医学工程师", "使用 Python 处理试验数据。", ["data"], "unrelated", {"other"}),
    ("安全研发工程师", "参与 Agent 安全研究。", ["ai_application"], "uncertain", {"security"}),
    ("CV算法工程师", "熟练使用 Python，熟悉 PyTorch。", ["computer_vision"], "aligned", {"computer_vision"}),
    ("CV算法工程师", "", ["frontend","backend"], "uncertain", {"computer_vision"}),
    ("后端开发实习生", "", ["backend"], "aligned", {"backend"}),
    ("AI应用开发实习生", "", ["ai_application"], "aligned", {"ai_application"}),
    ("算法工程师", "了解 OpenCV、Python 和 RAG 优先。", ["computer_vision"], "uncertain", set()),
    ("工程师", "任职要求：有后端开发经验。", ["backend"], "uncertain", set()),
    ("算法实习生", "无需 AI 开发经验。", ["ai_application"], "uncertain", set()),
    ("实习工程师", "不负责开发大模型应用。", ["ai_application"], "unrelated", set()),
    ("工程师", "本岗位不负责后端开发，重心为客户技术支持。", ["backend"], "unrelated", set()),
    ("实习生", "与负责后端开发的同事协作，跟进运营数据。", ["backend"], "uncertain", set()),
    ("软件工程师", "有过负责后端接口开发的经验。", ["backend"], "uncertain", set()),
    ("算法实习生（后端开发经验优先）", "熟悉Python。", ["backend"], "uncertain", set()),
    ("非后端开发岗位", "欢迎了解 Python 的同学。", ["backend"], "unrelated", set()),
    ("软件工程师", "工作职责：负责后端接口开发。", ["backend"], "aligned", {"backend"}),
    ("开发实习生", "任职要求：曾负责后端接口开发。", ["backend"], "uncertain", set()),
    ("前端／后端开发工程师", "", ["frontend"], "aligned", {"backend","frontend"}),
    ("前端开发与AI应用开发工程师", "", ["computer_vision","ai_application"], "aligned", {"frontend","ai_application"}),
    ("后端开发／产品经理", "", ["backend"], "aligned", {"backend","other"}),
    ("数据分析工程师", "", ["data"], "aligned", {"data"}),
    ("自动化测试工程师", "", ["test_development"], "aligned", {"test_development"}),
    ("DevOps实习生", "", ["devops"], "aligned", {"devops"}),
    ("Backend Engineer", "", ["backend"], "aligned", {"backend"}),
    ("安全研发工程师", "", [], "not_requested", set()),
]


@pytest.mark.parametrize("title,description,targets,status,labels", ROLE_CASES)
def test_fixed_manual_role_labels(title, description, targets, status, labels):
    source = job(title, description)
    result = evaluate_direction(source, targets)
    assert result.status == status
    assert set(result.detected_directions) == labels
    exact(result, source)
    if status == "not_requested":
        assert not result.evidence
    elif labels:
        assert result.evidence


SKILL_CASES = [
    ("任职要求：\n1、熟练使用Python, 熟悉Pytorch框架。", ["Python","PyTorch"], ["core","core"]),
    ("任职要求：能熟练使用pytorch、opencv等深度学习框架与工具。", ["PyTorch","OpenCV"], ["core","core"]),
    ("任职要求：熟悉 Python，Docker 使用经验优先。", ["Docker","Python"], ["bonus","core"]),
    ("掌握Python；PyTorch是加分项。", ["Python","PyTorch"], ["core","bonus"]),
    ("熟悉Python、SQL者优先。", ["Python","SQL"], ["bonus","bonus"]),
    ("加分项\n熟悉 Docker。\n任职要求\n掌握 SQL。", ["Docker","SQL"], ["bonus","core"]),
    ("岗位职责\n使用 Python 生成报表。", ["Python"], ["unclassified"]),
    ("岗位职责：使用 Python。任职要求：熟悉 Python。", ["Python"], ["core"]),
    ("无公开技术要求。", ["Git"], ["unclassified"]),
    ("Python是加分项。须熟练掌握Python。", ["Python"], ["unclassified"]),
    ("掌握Python、Matlab、C语言等至少一种编程或数据分析工具。", ["Python"], ["unclassified"]),
    ("任职要求：熟悉 Python 或 SQL。", ["Python","SQL"], ["unclassified","unclassified"]),
    ("无需掌握 Python。", ["Python"], ["unclassified"]),
    ("不熟悉Python也可以。", ["Python"], ["unclassified"]),
    ("不会Python也可。", ["Python"], ["unclassified"]),
    ("任职要求：Python 不是硬性要求。", ["Python"], ["unclassified"]),
    ("熟悉 Python，SQL、Docker 优先。", ["Python","SQL","Docker"], ["core","bonus","bonus"]),
    ("No Python required.", ["Python"], ["unclassified"]),
    ("不要求Python，但须掌握SQL。", ["Python","SQL"], ["unclassified","core"]),
    ("Python required. Docker preferred.", ["Python","Docker"], ["core","bonus"]),
    ("任职要求：掌握C++。", ["C","C++"], ["unclassified","core"]),
    ("任职要求：熟悉bs4。", ["Beautiful Soup"], ["core"]),
    ("任职要求：SQLAlchemy, GitHub Actions。", ["SQL","Git"], ["unclassified","unclassified"]),
    ("🙂任职要求：熟悉 Python。", ["Python"], ["core"]),
    (",熟悉 Python。", ["Python"], ["core"]),
]


@pytest.mark.parametrize("description,detected,expected", SKILL_CASES)
def test_fixed_manual_skill_labels(description, detected, expected):
    source = job(description=description)
    before = source.model_dump()
    items = classify_skill_requirements(source, detected, ["pYtHon", "bs4"])
    assert [item.skill for item in items] == detected
    assert [item.importance for item in items] == expected
    for item in items:
        assert item.matched == (item.skill in {"Python", "Beautiful Soup"})
        if item.importance != "unclassified":
            assert any(span.field == "description" for span in item.evidence)
        exact(item, source)
    assert source.model_dump() == before


def test_no_detected_skills_remains_empty_even_if_rule_recognizes_text():
    assert classify_skill_requirements(job(description="必须熟悉 Python。"), [], ["Python"]) == []


def test_heading_and_specific_skill_clause_are_both_quoted():
    source = job(description="任职要求：掌握 Python。\n加分项\nDocker 实践经验。")
    items = classify_skill_requirements(source, ["Docker","Python"], [])
    assert [span.text for span in items[0].evidence] == ["加分项","Docker 实践经验"]
    assert [span.text for span in items[1].evidence] == ["任职要求：","掌握 Python"]


def test_title_only_mention_is_not_a_required_skill():
    source = job(title="Python后端实习生")
    result, = classify_skill_requirements(source, ["Python"], [])
    assert result.importance == "unclassified" and result.evidence[0].field == "title"
    exact(result, source)


@pytest.mark.parametrize("importance", ["core", "bonus"])
def test_asserted_skill_strength_requires_description_evidence(importance):
    with pytest.raises(ValidationError):
        SkillRequirement(skill="Python", importance=importance, matched=False, evidence=[])


def test_determined_direction_requires_a_source_quote():
    with pytest.raises(ValidationError):
        DirectionFit(status="aligned", detected_directions=["backend"], reason="后端开发")


def row(job_id, *, eligibility="unknown", direction="aligned", core=(), bonus=(), score=50, count=1):
    skills = [SimpleNamespace(importance=kind, matched=matched)
              for kind, coverage in (("core",core),("bonus",bonus)) for matched in coverage]
    return SimpleNamespace(job=SimpleNamespace(id=job_id), eligibility=SimpleNamespace(overall=eligibility),
                           direction_fit=SimpleNamespace(status=direction), skill_requirements=skills,
                           match_score=score, matched_skills=["skill"] * count)


def test_order_quality_priorities_and_empty_category():
    options = [
        row(8, eligibility="met", direction="uncertain"),
        row(1, core=[True,True,False], score=40), row(2, core=[True,False], bonus=[True]*9, score=99),
        row(3, core=[False]), row(4, score=100), row(5, direction="uncertain", core=[True], score=100),
    ]
    assert [item.job.id for item in sorted(options, key=quality_rank_key)] == [8,1,2,3,4,5]


def test_equal_ratios_use_bonus_then_existing_score_matched_count_and_id():
    options = [row(1, core=[True,False], bonus=[True,False], score=70, count=2),
               row(2, core=[True,False]*2, bonus=[True,False], score=70, count=2),
               row(3, core=[True,False], bonus=[True], score=50, count=1),
               row(4, core=[True,False], bonus=[True,False], score=70, count=4),
               row(5, core=[True,False], bonus=[True,False], score=85)]
    assert [item.job.id for item in sorted(reversed(options), key=quality_rank_key)] == [3,5,4,1,2]
