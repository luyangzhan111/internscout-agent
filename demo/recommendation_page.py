"""Structured candidate entry and trustworthy Agent recommendation cards."""

from typing import Any

import streamlit as st

from demo.client import DemoClientError
from demo.condition_rendering import render_unknown_guidance
from demo.data_client import safe_http_url
from demo.data_rendering import SOURCE_LABELS, STATUS_LABELS, format_timestamp
from demo.eligibility_client import EligibilityResult
from demo.explanation_presenter import build_job_reasons
from demo.quality_rendering import render_direction, render_ranking_support, render_skill_requirements
from demo.recommendation_client import (
    AgentRecommendationResponse,
    RecommendationApiClient,
    RecommendedJob,
    build_recommendation_candidate,
)
from demo.recommendation_scope import DuplicateGroup, is_sample_record
from demo.recommendation_quality import DIRECTION_LABELS
from demo.ui import badges, info_item, job_heading, page_heading


_DRAFT_KEY = "recommendation_draft"
_RESULT_KEY = "recommendation_current_result"
_DEFAULTS = {
    "skills_text": "", "target_directions": [], "graduation_year": "", "degree": None, "degree_status": None,
    "work_experience_months": "", "city_mode": "unknown", "cities_text": "",
    "internship_months": "", "limit": 10, "explain_with_model": False, "include_samples": False,
}
_DEGREES = {
    None: "未填写", "below_associate": "大专以下", "associate": "大专",
    "bachelor": "本科", "master": "硕士", "doctor": "博士",
}
_DIMENSIONS = {
    "graduation_year": "毕业届次", "degree": "学历", "experience": "正式工作经验",
    "city": "城市", "internship_duration": "可实习时长",
}
_DECISIONS = {"met": "符合", "unknown": "待确认", "not_met": "不符合"}
_DECISION_TONES = {"met": "green", "unknown": "amber", "not_met": "red"}
_EVIDENCE_FIELDS = {"title": "岗位名称", "description": "岗位原文", "city": "工作城市"}
_SKILL_REASONS = {
    "full_match": "已识别技能全部覆盖", "partial_match": "已识别技能部分覆盖",
    "no_skill_match": "没有匹配技能", "insufficient_evidence": "岗位技能证据不足",
}


def _key(field: str) -> str:
    return f"recommendation_input_{field}"


def _render_inputs() -> dict[str, Any]:
    saved = st.session_state.get(_DRAFT_KEY, {})
    for field, default in _DEFAULTS.items():
        if _key(field) not in st.session_state:
            st.session_state[_key(field)] = saved.get(field, default)
    st.text_input("你的技能（至少一项，逗号分隔）", placeholder="Python，SQL", key=_key("skills_text"))
    st.multiselect(
        "目标岗位方向（可多选）", list(DIRECTION_LABELS), format_func=DIRECTION_LABELS.__getitem__,
        key=_key("target_directions"), placeholder="不限方向",
        help="选择后，明确无关的岗位会单列。原文不足以判断方向的岗位仍可进入推荐。",
    )
    st.caption("以下个人条件均可留空；本次填写只保留在浏览器会话，不保存为个人档案。")
    left, right = st.columns(2)
    with left:
        st.text_input("毕业年份（可选）", key=_key("graduation_year"), placeholder="例如 2027", max_chars=4)
        st.selectbox(
            "学历（可选）", list(_DEGREES), format_func=lambda value: _DEGREES[value],
            key=_key("degree"), placeholder="未填写",
        )
        st.selectbox(
            "学历状态", [None, "enrolled", "completed"], key=_key("degree_status"),
            format_func=lambda value: {None: "未说明", "enrolled": "在读", "completed": "已取得"}[value],
            placeholder="未说明",
        )
    with right:
        st.text_input(
            "正式工作经验（月，可选）", key=_key("work_experience_months"),
            placeholder="未填写与 0 个月不同", max_chars=4,
        )
        st.caption("不含实习和个人项目；填 0 表示没有正式工作经验，留空表示未提供。")
        st.text_input("可实习时长（月，可选）", key=_key("internship_months"), placeholder="例如 6", max_chars=3)
        st.selectbox(
            "可接受的城市", ["unknown", "selected", "unrestricted"], key=_key("city_mode"),
            format_func=lambda value: {"unknown": "未填写", "selected": "指定城市", "unrestricted": "不限城市"}[value],
        )
        st.text_input(
            "指定城市（逗号分隔）", key=_key("cities_text"), placeholder="深圳，北京",
            disabled=st.session_state[_key("city_mode")] != "selected",
        )
    st.number_input("最多展示岗位数", min_value=1, max_value=50, step=1, key=_key("limit"))
    st.checkbox("AI 补充说明", key=_key("explain_with_model"))
    st.caption("默认使用规则推荐，无需 API 密钥。开启后可请求已配置的模型补充说明。")
    st.checkbox("包含演示数据（仅用于体验）", key=_key("include_samples"))
    st.caption("默认排除样例与示例链接；相同岗位的重复记录合并展示，原始记录保留。")
    draft = {field: st.session_state[_key(field)] for field in _DEFAULTS}
    st.session_state[_DRAFT_KEY] = draft
    return draft


def render_agent_recommendations() -> None:
    page_heading(
        "04 / MATCH",
        "找到更适合你的下一站",
        "结合你的技能和投递条件整理岗位，把值得了解的机会排在前面。",
    )
    st.info(
        "推荐会比较投递条件、岗位方向和技能要求。投递条件覆盖毕业届次、学历、正式工作经验、城市和实习时长。"
    )
    with st.container(border=True, key="panel_recommendation_inputs"):
        st.subheader("从你的技能与条件开始")
        draft = _render_inputs()
    cached = st.session_state.get(_RESULT_KEY)
    if cached is not None and {"target_directions": [], **cached["draft"]} != draft:
        st.session_state.pop(_RESULT_KEY, None)
        st.info("输入已变化，上次结果已隐藏。请点击“获取推荐”重新判断。")

    left, right = st.columns(2)
    with left:
        requested = st.button("获取推荐", type="primary")
    with right:
        reset = st.button("刷新 / 清除旧结果")
    if reset:
        st.session_state.pop(_RESULT_KEY, None)
        st.info("旧结果已清除。准备好后点击“获取推荐”；本次操作不会请求 AI 说明。")
    st.caption("结果依据请求时的岗位内容。导入或更新岗位后，请重新获取推荐；页面不会自动重复请求。")

    if requested:
        st.session_state.pop(_RESULT_KEY, None)
        try:
            candidate = build_recommendation_candidate(**{
                field: value for field, value in draft.items()
                if field not in {"limit", "explain_with_model", "include_samples"}
            })
            with st.spinner("正在检查岗位条件与技能覆盖情况..."):
                result = RecommendationApiClient.from_env().recommend(
                    candidate=candidate, limit=draft["limit"], explain_with_model=draft["explain_with_model"],
                    include_samples=draft["include_samples"],
                )
            st.session_state[_RESULT_KEY] = {"draft": draft, "response": result}
        except (DemoClientError, ValueError) as exc:
            st.error(str(exc))

    cached = st.session_state.get(_RESULT_KEY)
    if cached is not None:
        _render_response(cached["response"])


def _render_response(response: AgentRecommendationResponse) -> None:
    st.subheader("规则推荐结果")
    st.text(response.summary)
    st.caption(f"判断时间：{format_timestamp(response.assessed_at)}")
    scope = getattr(response, "data_scope", None)
    if scope is None:
        st.warning("这份旧结果没有数据范围信息，无法确认演示数据隔离与重复合并情况。请更新服务后重新获取推荐。")
    else:
        st.caption(
            f"读取 {scope.total_records} 条原始记录 → 隔离 {scope.sample_records_excluded} 条演示记录"
            f" → 合并 {scope.duplicate_records_collapsed} 条重复记录 → 判断 {response.counts.evaluated} 个独立岗位"
        )
        if scope.include_samples:
            st.warning("演示模式：本次允许包含演示数据，标记的样例不代表真实招聘机会。")
    if response.explanation_status != "generated":
        notice = response.explanation_notice or {
            "disabled": "未启用 AI 补充说明，以上为规则结果。",
            "unavailable": "AI 补充说明暂不可用，以上规则结果仍可查看。",
            "failed": "AI 补充说明生成失败，以上规则结果仍可查看。",
            "stale": "岗位在生成说明期间发生变化，旧说明已舍弃；以上为重新计算的规则结果。",
            "not_needed": "本次无需生成 AI 补充说明。",
        }[response.explanation_status]
        st.info(notice)
    counts = response.counts
    has_quality = getattr(response, "ranking_version", None) in {"direction-core-v1", "direction-core-v2", "direction-evidence-v3", "direction-support-v4"}
    metric_counts = [("符合", counts.met), ("待确认", counts.unknown), ("不符合", counts.not_met), ("已关闭", counts.closed)]
    if has_quality:
        target_names = "、".join(DIRECTION_LABELS[key] for key in response.target_directions) or "不限方向"
        st.caption(f"本次目标方向：{target_names}")
        metric_counts.append(("方向不符", counts.direction_mismatch))
    for column, (label, count) in zip(st.columns(len(metric_counts)), metric_counts):
        column.metric(label, count)
    st.caption(f"共检查 {counts.evaluated} 个独立岗位，本次推荐 {counts.returned} 个。")
    if has_quality:
        if response.target_directions:
            st.caption("“符合”和“待确认”统计方向一致或方向待确认的岗位，明确与目标无关的岗位计入“方向不符”。")
        st.caption("投递条件符合的排在前面。组内依次比较岗位方向、核心技能、加分技能和总技能覆盖率。")
        if response.ranking_version == "direction-support-v4":
            st.caption("方向待确认时，先核对目标相关线索，再比较原技能覆盖；已有其他方向线索的岗位继续保留。")
    else:
        st.caption("这份结果使用旧版排序。投递条件符合的优先，同组按总技能覆盖率排列，未提供岗位方向和技能分类。")
    omitted = counts.met + counts.unknown - counts.returned
    if omitted:
        st.info(f"受展示上限限制，另有 {omitted} 个符合或待确认岗位未展示，可增加展示数量。")
    if counts.evaluated == 0:
        if scope is not None and scope.total_records:
            st.info("当前记录均为演示数据，已从本次推荐中隔离。请导入岗位，或勾选“包含演示数据（仅用于体验）”后重新获取推荐。")
        else:
            st.info("岗位库为空，请先到“导入与更新”添加岗位。")
    elif not response.recommendations:
        if has_quality and counts.direction_mismatch:
            if counts.direction_mismatch == counts.evaluated:
                st.info("本次没有与目标方向相符或方向待确认的岗位。可查看方向判断依据，或放宽目标方向、导入相关岗位后重新获取推荐。")
            else:
                st.info("当前目标方向下没有可推荐岗位。可查看下方的方向与投递条件依据，或放宽方向、导入相关岗位后重新获取推荐。")
        else:
            st.info("本次没有可推荐岗位：已检查岗位均存在明确阻断或已经关闭，请展开排除依据复核。")
    elif counts.met == 0:
        st.info("本次推荐均为待确认，仍需核对缺失或未明确的条件；待确认不等于通过。")

    reasons_by_job = build_job_reasons(response)
    if response.explanation_status == "generated":
        if reasons_by_job:
            st.caption(f"已整理 {len(reasons_by_job)} 个岗位的 AI 补充说明。推荐理由供参考，条件判断和原文依据请分别核对。")
        if len(reasons_by_job) < len(response.recommendations):
            scope = "部分" if reasons_by_job else "本次"
            st.info(f"{scope} AI 说明暂时无法对应到具体岗位，已保留规则结果。需要新的说明时，请点击“获取推荐”。")

    groups = {group.primary_job_id: group for group in getattr(response, "duplicate_groups", [])}
    # Preserve the validated server order; the model never supplies card order.
    for position, recommendation in enumerate(response.recommendations, 1):
        _render_card(
            recommendation, position, ai_reasons=reasons_by_job.get(recommendation.job.id),
            ai_expected=response.explanation_status == "generated",
            duplicate_group=groups.get(recommendation.job.id),
        )

    if has_quality and counts.direction_mismatch:
        excluded_by_direction = response.direction_excluded
        with st.expander(f"方向不符的岗位（展示 {len(excluded_by_direction)} 个 / 共 {counts.direction_mismatch} 个）"):
            st.caption("这些岗位因方向不同而单列。每个岗位的投递条件判断仍可单独核对。")
            for item in excluded_by_direction:
                job = item.job
                with st.container(border=True, key=f"direction_excluded_card_{job.id}"):
                    job_heading(job.title, job.company, job.city, salary=job.salary)
                    render_direction(item.direction_fit)
                    if is_sample_record(job.source, job.source_url):
                        st.warning("样例岗位，仅供演示，不代表真实招聘机会。")
                    st.text(f"实际投递条件：{_DECISIONS[item.eligibility.overall]}。{item.eligibility.reason}")
                    with st.expander("查看五项完整判断"):
                        _render_conditions(item.eligibility)
                    _render_source(item.eligibility, groups.get(job.id))

    blocked = counts.not_met + counts.closed
    if blocked:
        with st.expander(f"查看未推荐岗位的阻断依据（展示 {len(response.excluded)} 个 / 共 {blocked} 个）"):
            st.caption("以下岗位存在明确阻断或已关闭，未进入推荐列表。最多展示 10 个。")
            for result in response.excluded:
                with st.container(border=True, key=f"recommendation_excluded_card_{result.job.id}"):
                    job_heading(result.job.title, result.job.company, result.job.city, salary=result.job.salary)
                    badges([("未推荐", "red")])
                    if is_sample_record(result.job.source, result.job.source_url):
                        st.warning("样例岗位，仅供演示，不代表真实招聘机会。")
                    st.text(f"未推荐原因：{result.reason}")
                    for reason in result.blocking_reasons:
                        st.text(f"阻断原因：{reason}")
                    _render_conditions(result)
                    _render_source(result, groups.get(result.job.id))

def _render_card(
    recommendation: RecommendedJob, position: int,
    *, ai_reasons: list[str] | None = None, ai_expected: bool = False,
    duplicate_group: DuplicateGroup | None = None,
) -> None:
    result = recommendation.eligibility
    job = recommendation.job
    with st.container(border=True, key=f"recommendation_card_{job.id}"):
        job_heading(job.title, job.company, job.city, salary=job.salary, rank=position)
        badges([
            (f"投递条件：{_DECISIONS[result.overall]}", _DECISION_TONES[result.overall]),
        ])
        if is_sample_record(job.source, job.source_url):
            st.warning("样例岗位，仅供演示，不代表真实招聘机会。")
        st.text(result.reason)
        fit = getattr(recommendation, "direction_fit", None)
        if fit is not None:
            render_direction(fit)
            render_ranking_support(getattr(recommendation, "ranking_support", None))
        score, skills = st.columns([1, 2.2])
        with score:
            st.metric("已识别技能覆盖率", f"{recommendation.match_score}/100")
        with skills:
            st.text(f"匹配 {len(recommendation.matched_skills)} / 已识别 {len(recommendation.detected_job_skills)} 项")
            if fit is None:
                st.text("已匹配技能：" + ("、".join(recommendation.matched_skills) or "无"))
                st.text("缺失技能：" + ("、".join(recommendation.missing_skills) or "无"))
            if not recommendation.detected_job_skills:
                st.caption("岗位技能证据不足，尚未识别出可比较的技能；0 分不代表你没有能力。")
            else:
                st.caption("分母仅包含已识别的岗位技能，不是岗位全部要求，也不代表录用概率。")
        if fit is not None:
            render_skill_requirements(recommendation.skill_requirements)

        with st.container(key=f"explanation_reasons_{job.id}"):
            st.markdown("#### 推荐理由")
            if ai_reasons:
                st.caption("AI 补充说明 · 请结合下方条件与原文核对")
                for reason in ai_reasons:
                    st.text("• " + reason)
            else:
                st.caption("规则说明" if not ai_expected else "此岗位暂无可对应的 AI 理由，以下为规则说明。")
                st.text(_SKILL_REASONS[recommendation.reason])

        with st.container(key=f"recommendation_details_{job.id}"):
            pending, evidence = st.columns([1, 1.1])
            with pending:
                _render_pending_conditions(result)
            with evidence:
                _render_evidence(result)
        with st.expander("查看五项完整判断"):
            _render_conditions(result)
        with st.expander("查看完整岗位原文"):
            st.text(job.description)
        _render_source(result, duplicate_group)


def _render_pending_conditions(result: EligibilityResult) -> None:
    st.markdown("#### 待确认条件")
    checks = {check.dimension: check for check in result.checks}
    pending = [checks[dimension] for dimension in _DIMENSIONS if checks[dimension].status == "unknown"]
    if not pending:
        st.caption("本次核对的五项无待确认项；其他招聘要求仍需核实。")
        return
    for check in pending:
        info_item(_DIMENSIONS[check.dimension], check.reason, f"你的信息：{check.candidate_value}")
        render_unknown_guidance(check)


def _render_evidence(result: EligibilityResult) -> None:
    st.markdown("#### 原文依据")
    st.caption("以下文字直接来自岗位，不由 AI 改写。")
    checks = {check.dimension: check for check in result.checks}
    missing = []
    for dimension, label in _DIMENSIONS.items():
        check = checks[dimension]
        if not check.evidence:
            missing.append(label)
            continue
        with st.container(key=f"evidence_quote_{result.job.id}_{dimension}"):
            for quote in check.evidence:
                st.caption(f"{label} · {_EVIDENCE_FIELDS[quote.field]}")
                st.text(quote.text)
            for note in check.notes:
                st.caption(note)
    if missing:
        st.caption("未找到明确原文依据：" + "、".join(missing) + "。可查看完整原文或向招聘方核实。")


def _render_conditions(result: EligibilityResult) -> None:
    checks = {check.dimension: check for check in result.checks}
    for dimension, label in _DIMENSIONS.items():
        check = checks[dimension]
        st.text(
            f"{label}：{_DECISIONS[check.status]}\n原因：{check.reason}\n"
            f"你的信息：{check.candidate_value}\n岗位条件：{check.requirement}"
        )
        render_unknown_guidance(check)
        for evidence in check.evidence:
            st.caption(f"依据来自：{_EVIDENCE_FIELDS[evidence.field]}")
            st.text(evidence.text)
        if not check.evidence:
            st.caption("未找到可引用的明确岗位原文依据。")
        for note in check.notes:
            st.text(f"偏好 / 其他备注：{note}")


def _render_source(result: EligibilityResult, duplicate_group: DuplicateGroup | None = None) -> None:
    job = result.job
    st.caption(f"来源：{SOURCE_LABELS.get(job.source, job.source)} ｜ 招聘状态：{STATUS_LABELS[job.status]}")
    st.caption(f"{_checked_time_label(job.source)}：{format_timestamp(job.last_checked_at)} ｜ 记录更新：{format_timestamp(job.updated_at)}")
    url = safe_http_url(job.source_url)
    if url:
        st.link_button("前往岗位来源核对", url)
    if duplicate_group is not None:
        if duplicate_group.has_conflict:
            st.caption("合并来源存在差异，请展开核对；本卡片采用主来源的岗位原文。")
        with st.expander(f"查看合并来源（{len(duplicate_group.sources)} 条记录）"):
            st.text("主来源选择：" + duplicate_group.selection_reason)
            if duplicate_group.has_conflict:
                st.warning("来源记录存在差异。本卡片仅依据主来源判断，没有拼接其他版本的岗位原文。")
            else:
                st.caption("以下记录按同一岗位合并展示；本卡片仅依据主来源判断，其他来源保留供核对。")
            for source in duplicate_group.sources:
                role = "主来源" if source.job_id == duplicate_group.primary_job_id else "其他来源"
                st.text(
                    f"{role} · {SOURCE_LABELS.get(source.source, source.source)} · 记录 {source.job_id}\n"
                    f"{source.title} ｜ {source.company} ｜ {STATUS_LABELS[source.status]}"
                )
                st.caption(
                    f"{_checked_time_label(source.source)}：{format_timestamp(source.last_checked_at)} ｜ 记录更新：{format_timestamp(source.updated_at)}"
                )
                link = safe_http_url(source.source_url)
                if link:
                    st.link_button(f"核对{role}（记录 {source.job_id}）", link)


def _checked_time_label(source: str) -> str:
    return "最近核验" if source.strip().casefold() == "oppo" else "本地处理时间"
