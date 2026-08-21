"""Streamlit entry point for the InternScout product demo."""

import streamlit as st

from demo.client import (
    AgentApiClient,
    DemoClientError,
)
from demo.rendering import build_recommendation_views


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

    st.subheader("Agent Explanation")
    st.write(response.answer)

    views = build_recommendation_views(response)
    if response.recommendations is None:
        st.info("本次响应未包含结构化推荐数据。")
    elif not views:
        st.info("没有找到符合条件的岗位。")
    else:
        st.subheader("Recommended Jobs")
        for view in views:
            with st.container(border=True):
                st.markdown(
                    f"### {view.title}\n"
                    f"**公司：** {view.company}  "
                    f"**城市：** {view.city}  "
                    f"**薪资：** {view.salary}"
                )
                st.metric("匹配分数", view.score)
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
                    st.markdown(
                        f"[查看岗位来源]({view.source_url})"
                    )

    st.caption(
        f"Agent steps: {response.steps} · "
        f"Tool executions: {response.tool_execution_count}"
    )


def main() -> None:
    """Render the interactive product demo."""

    st.set_page_config(
        page_title="InternScout Agent Demo",
        page_icon="🔎",
        layout="centered",
    )
    st.title("InternScout Agent")
    st.caption(
        "Streamlit Demo → FastAPI → Agent Runtime → Matching"
    )

    skills_text = st.text_input(
        "Candidate skills",
        placeholder="Python, FastAPI, SQL",
    )
    preferred_city = st.text_input(
        "Preferred city",
        placeholder="深圳",
    )

    if not st.button("Find matching internships", type="primary"):
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
        st.error(f"Demo configuration error: {exc}")
        return

    _render_response(response)


if __name__ == "__main__":
    main()
