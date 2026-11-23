"""Display explicit uncertainty metadata without inferring it from prose."""

import streamlit as st

from demo.eligibility_client import EligibilityCheck


UNKNOWN_REASON_LABELS = {
    "candidate_missing": "个人信息缺失",
    "source_unspecified": "原文未说明",
    "interpretation_uncertain": "无法可靠判断",
    "requirements_conflict": "要求冲突",
}


def render_unknown_guidance(check: EligibilityCheck) -> None:
    if check.status != "unknown":
        return
    # Old session objects may predate these fields; never guess from reason text.
    label = UNKNOWN_REASON_LABELS.get(getattr(check, "unknown_reason", None))
    if label:
        st.caption(f"待确认类型：{label}")
    next_step = getattr(check, "next_step", "")
    if next_step:
        st.text(f"下一步：{next_step}")
