"""Chinese job-library and import pages backed exclusively by HTTP."""

from collections.abc import Callable

import streamlit as st

from demo.client import DemoClientError
from demo.data_client import (
    ImportRun,
    JobDataApiClient,
    LibraryJob,
    build_manual_import_payload,
    safe_http_url,
)
from demo.data_rendering import (
    RUN_STATUS_LABELS,
    SOURCE_LABELS,
    STATUS_LABELS,
    build_import_run_view,
    format_timestamp,
)
from demo.ui import badges, job_heading, page_heading, summary_strip


def _client() -> JobDataApiClient | None:
    try:
        return JobDataApiClient.from_env()
    except ValueError as exc:
        st.error(str(exc))
        return None


def render_job_library(open_imports: Callable[[], None]) -> None:
    page_heading(
        "01 / DISCOVER",
        "发现值得了解的机会",
        "按来源与招聘状态浏览岗位，展开查看原文；投递前请返回来源核验最新信息。",
    )
    client = _client()
    if client is None:
        return

    left, middle, right = st.columns([1.2, 1.2, 0.7])
    with left:
        source = st.selectbox(
            "数据来源", [None, "manual", "oppo", "mock"],
            format_func=lambda value: SOURCE_LABELS.get(value, "全部来源"),
            placeholder="全部来源",
        )
    with middle:
        status = st.selectbox(
            "岗位状态", [None, "unknown", "active", "closed"],
            format_func=lambda value: STATUS_LABELS.get(value, "全部状态"),
            placeholder="全部状态",
        )
    with right:
        page = int(st.number_input("页码", min_value=1, value=1, step=1))
    try:
        result = client.list_jobs(source=source, status=status, page=page)
    except DemoClientError as exc:
        st.error(str(exc))
        return

    summary_strip([
        ("筛选岗位", str(result.total)),
        ("当前页", f"{result.page} / {result.pages}" if result.pages else "—"),
        ("本页条数", str(len(result.items))),
    ])
    if not result.items:
        if result.total:
            st.info("当前页没有岗位，请选择较小的页码。")
        elif source is None and status is None and page == 1:
            _render_empty_library(client, open_imports)
        else:
            st.info("没有符合条件的岗位。可调整筛选，或前往“导入与更新”添加真实岗位。")
        return
    if any(job.source == "mock" for job in result.items):
        st.warning("本页包含样例数据，仅用于演示，不代表真实招聘机会。")
        st.caption("可前往「投递条件」查看样例的判断依据。使用「Agent 推荐」时，勾选「包含演示数据（仅用于体验）」。")
    for row_index, start in enumerate(range(0, len(result.items), 2)):
        with st.container(key=f"library_row_{row_index}"):
            columns = st.columns(2)
            for column, job in zip(columns, result.items[start:start + 2]):
                with column:
                    _render_job(job)


def _render_empty_library(
    client: JobDataApiClient, open_imports: Callable[[], None]
) -> None:
    st.info("导入一条真实岗位，或用项目自带的演示岗位试用。查看投递条件和原文依据无需 API 密钥。")
    left, right = st.columns(2)
    with left:
        st.button("导入真实岗位", on_click=open_imports, type="primary")
    with right:
        load_requested = st.button("加载演示岗位")
    if not load_requested:
        return
    try:
        loaded = client.load_samples()
    except DemoClientError as exc:
        st.error(str(exc))
        return
    if loaded.processed_count:
        st.rerun()
    st.warning("本次没有加载到演示岗位，请重试或导入真实岗位。")


def _render_job(job: LibraryJob) -> None:
    with st.container(border=True, key=f"library_card_{job.id}"):
        job_heading(
            job.title, job.company, job.city,
            salary=job.salary or "薪资未提供",
        )
        badges([
            (SOURCE_LABELS.get(job.source, job.source), "blue" if job.source == "oppo" else "neutral"),
            (STATUS_LABELS[job.status], {"unknown": "amber", "active": "green", "closed": "red"}[job.status]),
        ])
        st.caption(f"内容更新：{format_timestamp(job.updated_at)}")
        if job.status == "unknown":
            st.caption("待确认表示招聘状态尚未核实，不代表仍在招聘。")
        if job.source == "mock":
            st.caption("样例岗位，仅用于演示，不代表真实招聘机会。")
        with st.expander("查看岗位原文"):
            st.text(job.description)
            if job.skills:
                st.write("技能标签：" + "、".join(job.skills))
        with st.expander("来源与更新时间"):
            st.caption(f"来源：{SOURCE_LABELS.get(job.source, job.source)}")
            st.caption(f"内容更新：{format_timestamp(job.updated_at)}")
            st.caption(f"最近发现：{format_timestamp(job.last_seen_at)}")
            st.caption(f"最近核对：{format_timestamp(job.last_checked_at)}")
            if job.source == "manual":
                st.caption("手动导入的时间仅表示系统接收 / 处理，不表示已在线核验。")
            if job.published_at:
                st.caption(f"来源发布日期：{job.published_at.isoformat()}")
            if job.source_job_id:
                st.caption(f"来源岗位 ID：{job.source_job_id}")
        source_url = safe_http_url(job.source_url)
        if source_url:
            st.link_button("前往岗位来源核对 / 投递", source_url)
        else:
            st.caption("来源链接不可用，请在导入时补充有效的 HTTP(S) 链接。")


def _render_run(run: ImportRun) -> None:
    view = build_import_run_view(run)
    getattr(st, view.level)(view.title)
    st.write(view.counts)
    st.caption(f"记录 #{run.id} · 完成时间：{format_timestamp(run.finished_at)}")
    if view.note:
        st.caption(view.note)
    for warning in run.warnings:
        st.text(warning)
    for error in view.errors:
        st.text(error)


def render_imports() -> None:
    page_heading(
        "02 / IMPORT",
        "把机会整理进你的岗位库",
        "粘贴真实岗位，或手动刷新 OPPO 官网数据。手动导入时，再次提交相同来源链接会更新原记录。",
    )
    client = _client()
    if client is None:
        return

    manual_tab, oppo_tab = st.tabs(["手动导入岗位", "刷新 OPPO 岗位"])
    with manual_tab:
        _manual_form(client)
    with oppo_tab:
        _oppo_form(client)

    if "last_import_run" in st.session_state:
        st.subheader("最近一次操作结果")
        last_run = st.session_state["last_import_run"]
        _render_run(last_run)
        if last_run.job_ids:
            st.caption("接下来，前往「投递条件」填写已知条件并查看岗位原文依据。")

    st.subheader("近期导入 / 刷新记录")
    st.button("刷新记录", key="refresh_import_history")
    try:
        runs = client.list_imports(limit=10)
    except DemoClientError as exc:
        st.error(str(exc))
        return
    if not runs:
        st.info("还没有记录。首次导入后，这里会保留成功、部分完成和失败结果。")
    for run in runs:
        with st.expander(
            f"#{run.id} · {SOURCE_LABELS[run.source]} · "
            f"{RUN_STATUS_LABELS[run.status]} · {format_timestamp(run.started_at)}"
        ):
            _render_run(run)


def _manual_form(client: JobDataApiClient) -> None:
    st.info("未核实招聘状态时请保留“待确认”；导入成功不表示岗位仍在招聘。")
    with st.form("manual_job_import"):
        left, right = st.columns(2)
        with left:
            title = st.text_input("岗位名称 *", max_chars=100)
        with right:
            company = st.text_input("公司 *", max_chars=100)
        left, right = st.columns(2)
        with left:
            city = st.text_input("城市 *", max_chars=50)
        with right:
            source_url = st.text_input("岗位来源链接 *", placeholder="https://…", max_chars=2048)
        description = st.text_area("岗位原文 *", height=200, placeholder="粘贴岗位职责与任职要求", max_chars=50000)
        with st.expander("补充岗位信息（可选）"):
            left, right = st.columns(2)
            with left:
                salary = st.text_input("薪资（可选）", max_chars=100)
                skills_text = st.text_input("技能标签（可选，逗号分隔）")
                source_job_id = st.text_input(
                    "来源岗位 ID（可选）",
                    help="仅作来源标识记录。手动更新以相同来源链接为准；更换链接会新建岗位并保留旧记录。",
                    max_chars=200,
                )
            with right:
                published_at = st.text_input("发布日期（可选）", placeholder="YYYY-MM-DD")
                status = st.selectbox(
                    "当前招聘状态", ["unknown", "active", "closed"],
                    format_func=lambda value: STATUS_LABELS[value],
                    help="只有查看来源并确认后，才选择已确认在招或已关闭。",
                )
        st.caption(
            "更新已有岗位会替换完整信息；请展开核对招聘状态及其他可选信息，"
            "留空的可选内容会被清空。"
        )
        submitted = st.form_submit_button("保存 / 更新岗位", type="primary")
    if not submitted:
        return
    st.session_state.pop("last_import_run", None)
    try:
        payload = build_manual_import_payload(
            title=title, company=company, city=city, description=description,
            source_url=source_url, source_job_id=source_job_id, salary=salary,
            skills_text=skills_text, published_at=published_at, status=status,
        )
        with st.spinner("正在保存岗位..."):
            st.session_state["last_import_run"] = client.import_manual(payload)
    except (DemoClientError, ValueError) as exc:
        st.error(str(exc))


def _oppo_form(client: JobDataApiClient) -> None:
    st.caption("按关键词获取有限数量的岗位。受数量上限截断时会显示“部分完成”。")
    with st.form("oppo_job_refresh"):
        keyword = st.text_input("岗位关键词（可选）", placeholder="Python / 实习 / 算法", max_chars=100)
        left, right = st.columns(2)
        with left:
            max_pages = int(st.number_input("最多抓取页数", min_value=1, max_value=10, value=2))
        with right:
            max_jobs = int(st.number_input("最多处理岗位数", min_value=1, max_value=100, value=20))
        submitted = st.form_submit_button("从 OPPO 官网刷新", type="primary")
    if not submitted:
        return
    st.session_state.pop("last_import_run", None)
    try:
        with st.spinner("正在获取并更新 OPPO 岗位，请稍候..."):
            st.session_state["last_import_run"] = client.refresh_oppo(
                keyword=keyword, max_pages=max_pages, max_jobs=max_jobs
            )
    except DemoClientError as exc:
        st.error(str(exc))
