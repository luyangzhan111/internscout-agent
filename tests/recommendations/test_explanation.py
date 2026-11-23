"""Model formatting must not invent job associations or trigger repair calls."""

import json

import pytest

from app.recommendations.contracts import JobExplanation
from app.recommendations.explanation import parse_job_explanations


def document(*jobs):
    return json.dumps({"jobs": list(jobs)}, ensure_ascii=False)


def reason(job_id, text="你具备的 Python 技能与岗位开发工作相符。"):
    return {"job_id": job_id, "reasons": [text]}


def test_valid_complete_json_is_reordered_to_rule_order():
    raw = document(reason(7), reason(3, "你的 SQL 技能可以用于岗位中的数据查询工作。"))
    parsed = parse_job_explanations(raw, [3, 7])
    assert [item.job_id for item in parsed] == [3, 7]
    assert parsed[0].reasons == ["你的 SQL 技能可以用于岗位中的数据查询工作。"]


@pytest.mark.parametrize("wrapper", ["```json\n{}\n```", "```JSON\r\n{}\r\n```", "```\n{}\n```", " \n{}\n "])
def test_only_outer_json_wrapper_is_removed(wrapper):
    assert parse_job_explanations(wrapper.format(document(reason(4))), [4])[0].job_id == 4


@pytest.mark.parametrize("jobs", [
    [reason(1), reason(1)], [reason(1)], [reason(1), reason(2), reason(3)],
    [reason(1), reason(99)], [],
])
def test_duplicate_missing_or_extra_ids_fail_without_partial_results(jobs):
    with pytest.raises(ValueError):
        parse_job_explanations(document(*jobs), [1, 2])


@pytest.mark.parametrize("job_id", [True, False, "1", 1.0, 0, -1, None])
def test_ids_are_positive_strict_integers(job_id):
    with pytest.raises(ValueError):
        parse_job_explanations(document(reason(job_id)), [1])


@pytest.mark.parametrize("raw", [
    "这些只是旧版纯文本说明。", "说明：" + document(reason(1)),
    document(reason(1)) + "\n以上供参考。",
    '{"jobs":[],"jobs":[{"job_id":1,"reasons":["理由"]}]}',
    '{"jobs":[{"job_id":1,"job_id":2,"reasons":["理由"]}]}',
    '{"jobs":[{"job_id":NaN,"reasons":["理由"]}]}',
    '{"jobs":[{"job_id":Infinity,"reasons":["理由"]}]}',
    '[{"job_id":1,"reasons":["理由"]}]',
    '{"jobs":[{"job_id":1,"reasons":["理由"],"conditions":["伪造条件"]}]}',
    '{"jobs":[{"job_id":1,"reasons":["理由"]}],"summary":"额外内容"}',
])
def test_non_contract_outputs_are_rejected(raw):
    with pytest.raises(ValueError):
        parse_job_explanations(raw, [1])


@pytest.mark.parametrize("reasons", [
    [], ["理由"] * 4, [""], ["   "], [1], "一条理由", ["长" * 201],
    ["**具备 Python 技能**"], ["`match_score`为100"], ["# 推荐理由"],
    ["参考[来源](https://example.com)"], ["条件为not_met"], ["当前unknown状态"],
    ["assessed_at为今天"], ["overall为符合"], ["岗位为active"], ["状态closed"],
])
def test_reasons_are_short_nonempty_plain_text_without_internal_codes(reasons):
    with pytest.raises(ValueError):
        parse_job_explanations(document({"job_id": 1, "reasons": reasons}), [1])


def test_ordinary_technical_skill_names_are_allowed():
    result = JobExplanation(job_id=1, reasons=["  你掌握 Python、C++ 和 C#，并有 ReactiveX 开发经验，与岗位的开发技术相符。  "])
    assert result.reasons == ["你掌握 Python、C++ 和 C#，并有 ReactiveX 开发经验，与岗位的开发技术相符。"]


@pytest.mark.parametrize("code", [
    "unknown_reason", "next_step", "candidate_missing", "source_unspecified",
    "interpretation_uncertain", "requirements_conflict", "data_scope", "include_samples",
    "duplicate_groups", "is_sample", "primary_job_id", "last_checked_at",
    "target_directions", "direction_fit", "direction_mismatch", "ranking_version", "skill_requirements",
    "not_requested", "uncertain", "unrelated", "aligned", "core", "bonus", "unclassified",
])
def test_new_scope_and_uncertainty_codes_cannot_leak_into_job_reasons(code):
    with pytest.raises(ValueError):
        JobExplanation(job_id=1, reasons=[f"岗位的{code}需要核对。"])


def test_deeply_nested_json_is_a_format_failure():
    with pytest.raises(ValueError):
        parse_job_explanations("[" * 2000 + "0" + "]" * 2000, [1])


def test_core_ml_is_a_technical_name_and_can_touch_chinese_text():
    item = JobExplanation(job_id=1, reasons=["用户填写的Core ML与岗位涉及的工具有交集。"])
    assert item.reasons == ["用户填写的Core ML与岗位涉及的工具有交集。"]


def test_reason_lists_are_not_reused_between_results():
    first = parse_job_explanations(document(reason(1)), [1])
    first[0].reasons.append("调用方修改")
    second = parse_job_explanations(document(reason(1)), [1])
    assert len(second[0].reasons) == 1
