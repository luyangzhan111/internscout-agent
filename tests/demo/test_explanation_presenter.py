"""Pure-text reasons cannot be attached by title, rank, or guessed identity."""

from types import SimpleNamespace

import pytest

from demo.explanation_presenter import build_job_reasons, clean_ai_text
from demo.recommendation_client import JobExplanation


def response(text=None, *, ids=(7, 8), status="generated", structured=None):
    result = SimpleNamespace(
        recommendations=[SimpleNamespace(job=SimpleNamespace(id=job_id, title="同名岗位")) for job_id in ids],
        model_explanation=text, explanation_status=status,
    )
    if structured is not None:
        result.job_explanations = structured
    return result


LEGACY = """以下按规则顺序补充说明：
1. **ID 7 · CV算法工程师 · OPPO · 北京**（active）
- 技能覆盖率100%，Python、PyTorch、OpenCV与岗位原文有交集。
- 资格：overall=unknown，学历和毕业届次待确认。
  城市符合，实习时长还需核实。

2. **ID 8 · 同名岗位 · OPPO · 深圳**（active）
- 推荐理由：Python适用于岗位中的数据处理工作。
- 待确认：工作经验要求。

assessed_at: 2026-11-14T02:00:00+00:00
"""


def test_actual_legacy_id_headings_work_for_cache_without_new_attribute():
    cached = response(LEGACY)
    assert not hasattr(cached, "job_explanations")
    result = build_job_reasons(cached)
    assert result == {
        7: ["技能覆盖率100%，Python、PyTorch、OpenCV与岗位原文有交集。"],
        8: ["Python适用于岗位中的数据处理工作。"],
    }
    combined = " ".join(reason for reasons in result.values() for reason in reasons)
    assert not any(word in combined for word in ("资格", "待确认", "active", "unknown", "assessed_at", "ID"))


def test_structured_reasons_take_priority_and_remove_markdown():
    structured = [JobExplanation(job_id=7, reasons=["**Python** 技能有交集。"]),
                  JobExplanation(job_id=8, reasons=["使用 `PyTorch` 与 C++ 处理视觉任务。"])]
    assert build_job_reasons(response(LEGACY, structured=structured)) == {
        7: ["Python 技能有交集。"], 8: ["使用 PyTorch 与 C++ 处理视觉任务。"],
    }


@pytest.mark.parametrize("metadata", [
    "unknown_reason=candidate_missing", "source_unspecified", "interpretation_uncertain",
    "requirements_conflict", "data_scope", "include_samples=false", "duplicate_groups",
    "primary_job_id=7", "has_conflict=true", "sample_records_excluded=6", "is_sample=true",
    "target_directions=backend", "direction_fit=aligned", "skill_requirements=core",
    "direction_mismatch=5", "ranking_version=direction-core-v1",
])
def test_scope_metadata_in_ai_prose_is_hidden_without_discarding_other_reasons(metadata):
    structured = [JobExplanation(job_id=7, reasons=[f"推荐依据：{metadata}", "Python 与岗位技能有交集。"])]
    assert build_job_reasons(response(ids=(7,), structured=structured)) == {
        7: ["Python 与岗位技能有交集。"],
    }


@pytest.mark.parametrize("status", ["disabled", "unavailable", "failed", "stale", "not_needed"])
def test_explanations_are_never_displayed_for_non_generated_status(status):
    assert build_job_reasons(response(LEGACY, status=status)) == {}


def test_duplicate_ids_drop_all_ambiguous_sections_but_keep_other_explicit_ids():
    text = """ID 7 · 同名岗位
- 推荐理由：第一份说明。
ID 7 · 同名岗位
- 推荐理由：另一份说明。
ID 8 · 同名岗位
- 推荐理由：唯一对应的说明。
"""
    assert build_job_reasons(response(text)) == {8: ["唯一对应的说明。"]}


def test_unknown_ids_are_not_attached_to_an_existing_job():
    text = """ID 999 · 同名岗位
- 技能覆盖率100%，不能移给其他岗位。
ID 8 · 同名岗位
- 推荐理由：保留这个明确对应的说明。
"""
    assert build_job_reasons(response(text)) == {8: ["保留这个明确对应的说明。"]}


@pytest.mark.parametrize("text", [
    "1. 同名岗位\n- 推荐理由：Python有交集。\n2. 同名岗位\n- 推荐理由：PyTorch有交集。",
    "推荐理由：Python有交集。", "参考 ID 7 与 ID 8，推荐理由相同。",
    "ID 7 / ID 8\n- 推荐理由：联合说明不能归给单一岗位。",
    "ID 7/8\n- 推荐理由：联合说明不能归给单一岗位。",
    "ID 7.1\n- 推荐理由：不是ID7。",
])
def test_ambiguous_or_unlabelled_text_is_not_associated_by_order_or_title(text):
    assert build_job_reasons(response(text)) == {}


def test_explicit_ids_override_text_order_and_repeated_job_titles():
    text = """2. **ID 8 · 同名岗位**
- 推荐理由：PyTorch研究任务。
1. **ID 7 · 同名岗位**
- 推荐理由：Python后端任务。
"""
    result = build_job_reasons(response(text))
    assert list(result) == [7, 8]
    assert result[7] == ["Python后端任务。"]
    assert result[8] == ["PyTorch研究任务。"]


def test_reason_subsection_retains_bullets_and_stops_at_qualification():
    text = """### ID: 7 · 职位
推荐理由：
- Python服务开发。
- PyTorch视觉处理。
资格：
- 学历待确认。
- 未提供的工作经验不作推断。
"""
    assert build_job_reasons(response(text, ids=(7,))) == {7: ["Python服务开发。", "PyTorch视觉处理。"]}


def test_combined_line_keeps_only_explicit_skill_prefix():
    text = "ID 7 · 职位\n- 技能覆盖率100%，资格：overall=unknown，学历待确认。"
    assert build_job_reasons(response(text, ids=(7,))) == {7: ["技能覆盖率100%"]}


def test_clean_text_keeps_skill_names_numbers_and_plain_semantics():
    text = "## 推荐理由\n- **Python**、`PyTorch` 与 C++；技能覆盖率100%，3.5年经验，2027届。"
    assert clean_ai_text(text) == "推荐理由\nPython、PyTorch 与 C++；技能覆盖率100%，3.5年经验，2027届。"


def test_machine_metadata_and_state_tokens_are_removed():
    text = "**Python**匹配。 overall=unknown （active） ID 7\nassessed_at: 2026-11-14T02:00:00+00:00"
    assert clean_ai_text(text) == "Python匹配。"
    assert clean_ai_text("match_score=100；matched_skills=Python、PyTorch") == "技能覆盖率：100；匹配技能：Python、PyTorch"


def test_html_links_and_images_are_plain_text_without_active_targets():
    text = '<script>alert(1)</script><b>PyTorch</b>与[Python](https://example.com)。![图](https://example.com/a.png) <img src=x onerror=alert(2)> <a href="javascript:evil()">C++</a>'
    result = clean_ai_text(text)
    assert "PyTorch" in result and "Python" in result and "C++" in result
    assert not any(fragment in result for fragment in ("<", ">", "http", "javascript", "alert", "![", "]("))


def test_encoded_html_and_code_fences_cannot_create_active_content():
    text = "```text\n&lt;script&gt;alert(1)&lt;/script&gt;**PyTorch** 2.0\n```"
    assert clean_ai_text(text) == "PyTorch 2.0"


def test_empty_or_metadata_only_reasons_are_not_displayed():
    structured = [JobExplanation(job_id=7, reasons=["overall=unknown（active）"])]
    assert build_job_reasons(response(ids=(7,), structured=structured)) == {}


@pytest.mark.parametrize("heading", [
    "2. **岗位2（无ID）**", "2. **ID abc · 岗位2**", "2. **没有编号的新职位**",
    "### 岗位2（无ID）", "**岗位2（无ID）**", "ID abc · 岗位2", "2. **ID 8x · 岗位2**",
    "**应届毕业生岗位**", "### 正式工作经验丰富的工程师",
    "## 技能培训专员", "**工作内容策划师**", "### 推荐理由优化工程师",
])
def test_unidentified_new_job_heading_stops_previous_id_association(heading):
    text = f"""1. **ID 7 · 岗位1**（active）
- 技能覆盖率100%，第一岗位的Python依据。
{heading}
- 技能覆盖率100%，这段绝不能挂到岗位1。
3. **ID 8 · 岗位3**（active）
- 推荐理由：第三岗位独立的PyTorch依据。
"""
    result = build_job_reasons(response(text))
    assert result == {
        7: ["技能覆盖率100%，第一岗位的Python依据。"],
        8: ["第三岗位独立的PyTorch依据。"],
    }
