"""Streamlit entry point for the InternScout product demo."""

import streamlit as st

from demo.client import (
    AgentApiClient,
    DemoClientError,
)
from demo.data_page import render_imports, render_job_library
from demo.data_rendering import SOURCE_LABELS, STATUS_LABELS
from demo.eligibility_page import render_eligibility
from demo.recommendation_page import render_agent_recommendations
from demo.rendering import build_recommendation_views
from demo.ui import install_design_system, render_brand


_PAGE_KEY = "workspace_page"


def _open_imports() -> None:
    st.session_state[_PAGE_KEY] = "导入与更新"


def _build_user_message(
    skills: list[str],
    preferred_city: str,
) -> str:
    """Describe the user's matching request to the existing Agent API."""

    city_text = preferred_city or "不限城市"
    skills_text = "、".join(skills)
    return (
        "请根据候选人技能："
        f"{skills_text}，意向城市：{city_text}，"
        "推荐实习岗位，并说明匹配分数、已匹配技能、"
        "缺失技能和推荐理由。"
    )


def _render_response(response: object) -> None:
    """Render a validated Agent response in the Streamlit page."""

    st.subheader("推荐说明")
    st.write(response.answer)

    views = build_recommendation_views(response)
    if response.recommendations is None:
        st.info("本次响应未包含结构化推荐数据。")
    elif not views:
        st.info("没有找到符合条件的岗位。")
    else:
        st.subheader("推荐岗位")
        for view in views:
            with st.container(border=True):
                if view.source == "mock":
                    st.warning("样例岗位，仅用于演示，不代表真实招聘机会。")
                st.markdown(
                    f"### {view.title}\n"
                    f"**公司：** {view.company}  "
                    f"**城市：** {view.city}  "
                    f"**薪资：** {view.salary}"
                )
                st.caption(
                    f"来源：{SOURCE_LABELS.get(view.source, view.source or '未提供')} ｜ "
                    f"状态：{STATUS_LABELS.get(view.status, STATUS_LABELS['unknown'])}"
                )
                st.metric("已识别技能覆盖率", view.score)
                st.write(
                    "已匹配技能：",
                    view.matched_skills,
                )
                st.write(
                    "缺失技能：",
                    view.missing_skills,
                )
                st.write("匹配说明：", view.reason)
                if view.source_url:
                    st.link_button("查看岗位来源", view.source_url)

    st.caption(
        f"分析轮次：{response.steps} · "
        f"工具调用：{response.tool_execution_count}"
    )


def main() -> None:
    """Render the interactive product demo."""

    st.set_page_config(
        page_title="InternScout 求职助手",
        page_icon="🔎",
        layout="wide",
    )
    install_design_system()
    render_brand()
    with st.container(key="workspace_nav"):
        page = st.radio(
            "功能", ["岗位库", "导入与更新", "投递条件", "Agent 推荐"],
            horizontal=True, label_visibility="collapsed", key=_PAGE_KEY,
        )
    pages = {"岗位库": lambda: render_job_library(_open_imports), "导入与更新": render_imports,
             "投递条件": render_eligibility, "Agent 推荐": render_agent_recommendations}
    with st.container(key=f"page_{list(pages).index(page)}"):
        pages[page]()


def _render_agent_page() -> None:
    st.subheader("Agent 推荐")
    st.caption("需要配置 AI 模型。技能覆盖率只反映已识别的技能，不等于投递资格或录用概率。")

    skills_text = st.text_input(
        "你的技能（英文逗号分隔）",
        placeholder="Python, FastAPI, SQL",
    )
    preferred_city = st.text_input(
        "意向城市（可选）",
        placeholder="深圳",
    )

    if not st.button("查找匹配岗位", type="primary"):
        return

    skills = [
        skill.strip()
        for skill in skills_text.split(",")
        if skill.strip()
    ]
    if not skills:
        st.warning("请至少输入一项技能。")
        return

    user_message = _build_user_message(
        skills,
        preferred_city.strip(),
    )

    try:
        with st.spinner("Agent 正在分析岗位..."):
            response = AgentApiClient.from_env().query(
                user_message
            )
    except DemoClientError as exc:
        st.error(str(exc))
        return
    except ValueError as exc:
        st.error(f"推荐服务配置有误：{exc}")
        return

    _render_response(response)


if __name__ == "__main__":
    main()
