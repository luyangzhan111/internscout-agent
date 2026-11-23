"""Session-only candidate input and evidence-based eligibility results."""

from typing import Any

import streamlit as st

from demo.client import DemoClientError
from demo.condition_rendering import render_unknown_guidance
from demo.data_client import JobDataApiClient, safe_http_url
from demo.data_rendering import SOURCE_LABELS, STATUS_LABELS, format_timestamp
from demo.eligibility_client import (
    EligibilityApiClient,
    EligibilityResponse,
    EligibilityResult,
    build_eligibility_profile,
    job_snapshot,
    results_match_current_jobs,
)
from demo.ui import badges, job_heading, page_heading
from demo.recommendation_scope import is_sample_record


_DRAFT_KEY = "eligibility_draft"
_RESULT_KEY = "eligibility_current_result"
_FIELDS = {
    "graduation_year": "",
    "degree": None,
    "degree_status": None,
    "work_experience_months": "",
    "city_mode": "unknown",
    "cities_text": "",
    "internship_months": "",
    "source": None,
    "status": None,
    "page": 1,
}
_DEGREE_LABELS = {
    None: "未填写", "below_associate": "大专以下", "associate": "大专",
    "bachelor": "本科", "master": "硕士", "doctor": "博士",
}
_DECISION_LABELS = {"met": "符合", "not_met": "不符合", "unknown": "待确认"}
_DECISION_TONES = {"met": "green", "not_met": "red", "unknown": "amber"}
_DIMENSION_LABELS = {
    "graduation_year": "毕业届次", "degree": "学历", "experience": "正式工作经验",
    "city": "城市", "internship_duration": "可实习时长",
}
_EVIDENCE_FIELDS = {"title": "岗位名称", "description": "岗位原文", "city": "工作城市"}


def _key(field: str) -> str:
    return f"eligibility_input_{field}"


def _reset_page() -> None:
    st.session_state[_key("page")] = 1


def _render_inputs() -> dict[str, Any]:
    # Separate draft keys survive Streamlit's cleanup of off-page widgets.
    saved = st.session_state.get(_DRAFT_KEY, {})
    for field, default in _FIELDS.items():
        if _key(field) not in st.session_state:
            st.session_state[_key(field)] = saved.get(field, default)

    st.caption("所有条件都可留空；仅保留在本次浏览器会话，不保存为数据库档案。")
    left, right = st.columns(2)
    with left:
        st.text_input("毕业年份（可选）", key=_key("graduation_year"), placeholder="例如 2027", max_chars=4)
        st.selectbox("学历（可选）", list(_DEGREE_LABELS),
                     format_func=lambda value: _DEGREE_LABELS[value], key=_key("degree"),
                     placeholder="未填写")
        st.selectbox(
            "学历状态", [None, "enrolled", "completed"],
            format_func=lambda value: {None: "未说明", "enrolled": "在读", "completed": "已取得"}[value],
            key=_key("degree_status"), placeholder="未说明",
        )
    with right:
        st.text_input(
            "正式工作经验（月，可选）", key=_key("work_experience_months"),
            placeholder="未填写与 0 个月不同",
            help="只计算正式工作经验，不把实习或个人项目时长算进去。",
            max_chars=4,
        )
        st.caption("正式工作经验不含实习和个人项目；填 0 表示没有正式工作经验，留空表示未提供。")
        st.text_input("可实习时长（月，可选）", key=_key("internship_months"), placeholder="例如 6", max_chars=3)
        st.selectbox(
            "可接受的城市", ["unknown", "selected", "unrestricted"],
            format_func=lambda value: {"unknown": "未填写", "selected": "指定城市", "unrestricted": "不限城市"}[value],
            key=_key("city_mode"),
        )
        # Keep this widget present so switching modes does not discard the draft.
        st.text_input(
            "指定城市（逗号分隔）", key=_key("cities_text"),
            disabled=st.session_state[_key("city_mode")] != "selected", placeholder="深圳，北京",
        )

    st.subheader("选择本次要判断的岗位")
    left, right = st.columns(2)
    with left:
        st.selectbox(
            "岗位来源", [None, "manual", "oppo", "mock"], key=_key("source"),
            format_func=lambda value: SOURCE_LABELS.get(value, "全部来源"), on_change=_reset_page,
            placeholder="全部来源",
        )
    with right:
        st.selectbox(
            "招聘状态", [None, "unknown", "active", "closed"], key=_key("status"),
            format_func=lambda value: STATUS_LABELS.get(value, "全部状态"), on_change=_reset_page,
            placeholder="全部状态",
        )
    st.number_input("岗位页码", min_value=1, step=1, key=_key("page"))
    draft = {field: st.session_state[_key(field)] for field in _FIELDS}
    st.session_state[_DRAFT_KEY] = draft
    return draft


def render_eligibility() -> None:
    page_heading(
        "03 / CHECK",
        "先核对条件，再决定投递",
        "把你的条件与岗位原文放在一起，逐项看清符合之处和需要确认的问题。",
    )
    st.info(
        "仅检查毕业届次、学历、正式工作经验、城市和实习时长五类明确条件。"
        "“待确认”不等于通过；“符合”也不代表满足全部招聘要求或保证录用。"
    )
    with st.container(border=True, key="panel_eligibility_inputs"):
        st.subheader("你的投递条件")
        draft = _render_inputs()
    st.button("刷新当前页岗位", key="eligibility_refresh_jobs")
    try:
        jobs_page = JobDataApiClient.from_env().list_jobs(
            source=draft["source"], status=draft["status"], page=draft["page"], page_size=20
        )
    except (DemoClientError, ValueError) as exc:
        st.session_state.pop(_RESULT_KEY, None)
        st.error(str(exc))
        return

    jobs = jobs_page.items
    context = {"draft": draft, "jobs": [job_snapshot(job) for job in jobs]}
    cached = st.session_state.get(_RESULT_KEY)
    if cached is not None and cached["context"] != context:
        st.session_state.pop(_RESULT_KEY, None)
        st.info("填写条件、筛选或当前岗位内容已变化，上次判断已隐藏，请重新判断。")

    st.caption(
        f"本次只判断当前页 {len(jobs)} 个岗位（每页最多 20 个）；"
        f"筛选结果共 {jobs_page.total} 个，第 {jobs_page.page} / {jobs_page.pages} 页。"
    )
    if any(is_sample_record(job.source, job.source_url) for job in jobs):
        st.warning("当前页包含样例岗位，仅供演示，不代表真实招聘机会。")
    with st.expander("查看本页待判断岗位"):
        for job in jobs:
            st.text(f"{job.title} ｜ {job.company} ｜ {job.city}")
    if not jobs:
        st.session_state.pop(_RESULT_KEY, None)
        st.info("当前页没有岗位，请调整来源、状态或页码。")

    if st.button(f"判断当前页的 {len(jobs)} 个岗位", type="primary", disabled=not jobs):
        st.session_state.pop(_RESULT_KEY, None)
        try:
            profile = build_eligibility_profile(**{
                field: draft[field] for field in _FIELDS if field not in {"source", "status", "page"}
            })
            with st.spinner("正在逐项核对岗位原文..."):
                response = EligibilityApiClient.from_env().evaluate(
                    profile=profile, job_ids=[job.id for job in jobs]
                )
            if not results_match_current_jobs(response, jobs):
                st.warning("岗位原文或状态刚刚发生变化，本次结果已隐藏，请刷新页面后重新判断。")
            else:
                st.session_state[_RESULT_KEY] = {"context": context, "response": response}
        except (DemoClientError, ValueError) as exc:
            st.error(str(exc))

    cached = st.session_state.get(_RESULT_KEY)
    if cached is not None:
        _render_response(cached["response"])


def _render_response(response: EligibilityResponse) -> None:
    st.subheader("当前页判断结果")
    st.caption(f"判断时间：{format_timestamp(response.assessed_at)}")
    columns = st.columns(3)
    for column, status in zip(columns, ("met", "not_met", "unknown")):
        column.metric(_DECISION_LABELS[status], sum(item.overall == status for item in response.items))
    for result in response.items:
        _render_result(result)


def _render_result(result: EligibilityResult) -> None:
    job = result.job
    with st.container(border=True, key=f"eligibility_card_{job.id}"):
        job_heading(job.title, job.company, job.city, salary=job.salary)
        badges([
            (f"总评：{_DECISION_LABELS[result.overall]}", _DECISION_TONES[result.overall]),
            ("五项条件核对", "neutral"),
        ])
        st.caption(
            f"来源：{SOURCE_LABELS.get(job.source, job.source)} ｜ 招聘状态：{STATUS_LABELS[job.status]}"
        )
        if is_sample_record(job.source, job.source_url):
            st.warning("样例岗位，仅用于演示。")
        st.text(result.reason)
        for reason in result.blocking_reasons:
            st.text(f"阻断原因：{reason}")
        with st.expander("查看五项判断与原文依据"):
            checks = {check.dimension: check for check in result.checks}
            for dimension, label in _DIMENSION_LABELS.items():
                check = checks[dimension]
                st.text(
                    f"{label}：{_DECISION_LABELS[check.status]}\n"
                    f"原因：{check.reason}\n你的信息：{check.candidate_value}\n"
                    f"岗位条件：{check.requirement}"
                )
                render_unknown_guidance(check)
                if check.evidence:
                    for evidence in check.evidence:
                        st.caption(f"依据来自：{_EVIDENCE_FIELDS[evidence.field]}")
                        st.text(evidence.text)
                else:
                    st.caption("未找到可引用的明确岗位原文依据。")
                for note in check.notes:
                    st.text(f"偏好 / 其他备注：{note}")
        with st.expander("查看完整岗位原文"):
            st.text(job.description)
        link = safe_http_url(job.source_url)
        if link:
            st.link_button("前往岗位来源核对", link)
