"""Direction and requirement details shown in recommendation cards."""

import streamlit as st

from demo.eligibility_client import EligibilityEvidence
from demo.recommendation_quality import DIRECTION_LABELS, DirectionFit, RankingSupport, SkillRequirement


_DIRECTION_STATES = {
    "aligned": "方向一致", "uncertain": "方向待确认",
    "unrelated": "方向不符", "not_requested": "不限方向",
}
_CATEGORIES = {"core": "核心技能", "bonus": "加分技能", "unclassified": "未分类技能"}
_FIELDS = {"title": "岗位名称", "description": "岗位原文", "city": "工作城市"}


def _quote(evidence: EligibilityEvidence) -> None:
    st.caption(_FIELDS[evidence.field])
    st.text(evidence.text)


def render_direction(fit: DirectionFit) -> None:
    detected = "、".join(DIRECTION_LABELS.get(direction, "其他方向") for direction in fit.detected_directions)
    if fit.target_checks:
        states = {"aligned": "有匹配依据", "unrelated": "明确无关", "uncertain": "证据不足，待确认"}
        st.text("目标方向 · " + states[fit.status])
        if detected:
            st.caption("已有方向线索：" + detected + "。其他目标需分别核对。")
        st.text(fit.reason)
        for check in fit.target_checks:
            st.text(DIRECTION_LABELS[check.target] + " · " + states[check.status])
            st.caption(check.reason)
        with st.expander("各目标方向的原文依据"):
            assigned = [span for check in fit.target_checks for span in check.evidence]
            for check in fit.target_checks:
                st.text(DIRECTION_LABELS[check.target] + " · " + states[check.status])
                if not check.evidence:
                    st.caption("未找到足以确认或排除该方向的原文，建议核对完整岗位。")
                for span in check.evidence:
                    _quote(span)
            remaining = [span for span in fit.evidence if span not in assigned]
            if remaining:
                st.text("其他原文线索（不代表目标已匹配）")
                for span in remaining:
                    _quote(span)
        return
    st.text("岗位方向 · " + _DIRECTION_STATES[fit.status] + (f"（{detected}）" if detected else ""))
    if fit.status == "not_requested":
        return
    st.text(fit.reason)
    if fit.evidence:
        with st.expander("方向判断的原文依据"):
            for span in fit.evidence:
                _quote(span)


def render_ranking_support(support: RankingSupport | None) -> None:
    if support is None or support.level == "not_applicable":
        return
    labels = {"target_specific": "有目标相关线索", "insufficient": "目标相关证据仍不足", "other_direction": "已有其他方向线索"}
    st.text("排序参考 · " + labels[support.level])
    st.caption(support.reason)
    if support.targets:
        st.text("线索对应目标：" + "、".join(DIRECTION_LABELS[target] for target in support.targets))
    if support.matched_target_skills:
        st.text("相关匹配技能：" + "、".join(support.matched_target_skills))
    st.caption("用于方向待确认岗位的组内排序，仍需核对投递条件和岗位职责。")
    if support.evidence:
        with st.expander("排序参考的原文"):
            for span in support.evidence:
                _quote(span)


def render_skill_requirements(requirements: list[SkillRequirement]) -> None:
    if not requirements:
        return
    for importance, label in _CATEGORIES.items():
        rows = [row for row in requirements if row.importance == importance]
        if not rows:
            st.caption(f"{label} · 未识别到此类技能")
            continue
        covered = [row.skill for row in rows if row.matched]
        missing = [row.skill for row in rows if not row.matched]
        st.text(
            f"{label} · 匹配 {len(covered)} / {len(rows)} 项\n"
            f"已匹配：{'、'.join(covered) or '无'}　未匹配：{'、'.join(missing) or '无'}"
        )
    with st.expander("技能分类的原文依据"):
        for row in requirements:
            st.text(f"{row.skill} · {_CATEGORIES[row.importance]}")
            if not row.evidence:
                st.caption("缺少能说明技能重要性的原文。")
            for span in row.evidence:
                _quote(span)
