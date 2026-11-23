"""New direction uncertainty is visible and cannot be mislabeled by the client."""

import copy

import httpx
import pytest

from demo.explanation_presenter import build_job_reasons
from demo.recommendation_client import JobExplanation
from tests.demo.test_explanation_presenter import response
from demo.recommendation_client import AgentRecommendationResponse, RecommendationApiClient, build_recommendation_candidate
from tests.demo.test_recommendation_client import _quality_payload
from tests.demo.test_recommendation_page import _field, _fill_skills, _recommend, _start


def evidence_payload():
    payload = _quality_payload()
    payload["ranking_version"] = "direction-evidence-v3"
    payload["target_directions"] = ["ai_application", "computer_vision"]
    cards = [*payload["recommendations"], *payload["direction_excluded"]]
    for index, card in enumerate(cards):
        title = ("AI应用工程师", "后端开发工程师", "公关营销")[index]
        card["job"]["title"] = title
        card["eligibility"]["job"] = copy.deepcopy(card["job"])
        quote = {"field": "title", "text": title, "start": 0, "end": len(title)}
        states = (("aligned", "uncertain"), ("uncertain", "uncertain"), ("unrelated", "unrelated"))[index]
        overall = ("aligned", "uncertain", "unrelated")[index]
        card["direction_fit"] = {
            "status": overall, "detected_directions": (["ai_application"], ["backend"], ["other"])[index],
            "reason": "每个目标分别判断，已有线索不证明其他方向无关。", "evidence": [quote],
            "target_checks": [{"target": target, "status": status,
                               "reason": "原文有对应职能依据。" if status != "uncertain" else "未找到足以确认或排除该目标的证据。",
                               "evidence": [quote] if status != "uncertain" else []}
                              for target, status in zip(payload["target_directions"], states, strict=True)],
        }
    return payload


def test_v3_keeps_known_other_direction_clues_without_claiming_the_target_is_unrelated():
    payload = evidence_payload()
    client = RecommendationApiClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)))
    result = client.recommend(candidate=build_recommendation_candidate(
        skills_text="Python", target_directions=["ai_application", "computer_vision"]))
    partial = result.recommendations[1].direction_fit
    assert partial.status == "uncertain" and partial.detected_directions == ["backend"]
    assert [check.status for check in partial.target_checks] == ["uncertain", "uncertain"]
    assert result.direction_excluded[0].direction_fit.status == "unrelated"


@pytest.mark.parametrize("defect", ["missing", "reversed", "duplicate", "aggregate", "no_quote", "bad_quote",
                                    "outside_snapshot", "old_version", "positive_conflict", "unknown_target", "blank_reason"])
def test_v3_rejects_incomplete_or_unverifiable_target_decisions(defect):
    payload = evidence_payload()
    fit = payload["recommendations"][0]["direction_fit"]
    check = fit["target_checks"][0]
    if defect == "missing": fit["target_checks"].pop()
    elif defect == "reversed": fit["target_checks"].reverse()
    elif defect == "duplicate": fit["target_checks"].append(copy.deepcopy(check))
    elif defect == "aggregate": fit["status"] = "unrelated"
    elif defect == "no_quote": check["evidence"] = []
    elif defect == "bad_quote": check["evidence"][0]["text"] = "未在原文出现的职责"
    elif defect == "outside_snapshot":
        check["evidence"] = [{"field": "title", "text": "AI", "start": 0, "end": 2}]
    elif defect == "old_version": payload["ranking_version"] = "direction-core-v2"
    elif defect == "positive_conflict": check["status"] = "unrelated"
    elif defect == "unknown_target": check["target"] = "unknown_role"
    elif defect == "blank_reason": check["reason"] = "  "
    with pytest.raises(ValueError):
        AgentRecommendationResponse.model_validate(payload)


def test_v3_page_shows_each_target_and_uncertainty_in_plain_language(monkeypatch):
    app, _, requests = _start(monkeypatch, evidence_payload())
    _fill_skills(app)
    _field(app.multiselect, "目标岗位方向（可多选）").set_value(["ai_application", "computer_vision"]).run()
    _recommend(app)
    assert not app.error
    texts = "\n".join(item.value for item in app.text)
    assert "AI 应用开发 · 有匹配依据" in texts
    assert "计算机视觉 · 证据不足，待确认" in texts
    assert "计算机视觉 · 明确无关" in texts
    assert "其他原文线索（不代表目标已匹配）" in texts
    assert not any("target_checks" in text for text in (item.value for item in app.text))
    assert len([request for request in requests if request.method == "POST"]) == 1


@pytest.mark.parametrize("text", ["target_checks=uncertain", "direction-evidence-v3 该岗位符合"])
def test_new_internal_direction_fields_are_not_displayed_as_ai_reasons(text):
    result = response(ids=(7,), structured=[JobExplanation(
        job_id=7, reasons=[text, "Python 与岗位技能有交集。"])])
    assert build_job_reasons(result) == {7: ["Python 与岗位技能有交集。"]}
