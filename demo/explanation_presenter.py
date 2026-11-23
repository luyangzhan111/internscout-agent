"""Pure-text AI reasons with conservative, explicit job-ID association."""

from __future__ import annotations

from collections import Counter
from html import unescape
from html.parser import HTMLParser
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from demo.recommendation_client import AgentRecommendationResponse


class _PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.blocked: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "iframe", "object", "svg", "math"}:
            self.blocked = tag
        elif tag in {"br", "p", "div", "li"} and self.blocked is None:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == self.blocked:
            self.blocked = None
        elif tag in {"p", "div", "li"} and self.blocked is None:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.blocked is None:
            self.parts.append(data)


_STATES = r"(?:not_met|unknown|active|closed|met|generated|disabled|unavailable|failed|stale|not_needed)"
_JOB_HEADER = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:(?:\d+[.)、]|[-*+])\s*)?"
    r"(?:\*\*|__|`)?\s*(?:岗位\s*)?(?:ID|编号)\s*[:：#]?\s*(\d+)(?!\w)", re.I
)
_QUALIFICATION = re.compile(
    r"资格|投递条件|待确认|毕业|届次|学历|经验要求|实习时长|可实习|到岗|招聘状态|"
    r"状态\s*[:：]|\boverall\b|\beligibility\b|\bstatus\b", re.I
)
_REASON_START = re.compile(r"^(?:推荐理由|推荐原因|匹配理由|匹配亮点|技能|技术匹配|工作内容|职责契合)")
_TRUST_METADATA = re.compile(
    r"(?<![A-Za-z0-9_])(?:unknown_reason|next_step|candidate_missing|source_unspecified|"
    r"interpretation_uncertain|requirements_conflict|data_scope|include_samples|duplicate_groups|"
    r"primary_job_id|has_conflict|selection_reason|total_records|sample_records_excluded|"
    r"duplicate_records_collapsed|is_sample|target_directions|direction_fit|skill_requirements|"
    r"direction_mismatch|direction_excluded|ranking_version|detected_directions|target_checks|direction-evidence-v\d+|"
    r"ranking_support|matched_target_skills|target_specific|other_direction|not_applicable|direction-support-v\d+|not_requested)(?![A-Za-z0-9_])", re.I,
)


def clean_ai_text(text: str) -> str:
    """Remove presentation syntax and machine metadata; retain plain facts.

    Callers must display this using a plain-text widget, never HTML/Markdown.
    No URL or media is fetched while cleaning.
    """

    if not isinstance(text, str):
        return ""
    value = unescape(text)
    value = re.sub(r"^\s*```[^\n]*$", "", value, flags=re.M)
    value = re.sub(r"!\[[^\]]*\](?:\([^\n]*?\)|\[[^\]]*\])", "", value)
    value = re.sub(r"\[([^\]]+)\]\([^\n]*?\)", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", value)
    value = re.sub(r"^\s*\[[^\]]+\]:\s*\S+.*$", "", value, flags=re.M)
    value = re.sub(r"<(?:https?://|mailto:)[^>]+>", "", value, flags=re.I)
    parser = _PlainHTML()
    parser.feed(value)
    parser.close()
    value = "".join(parser.parts)
    value = value.replace("`", "").replace("*", "").replace("__", "").replace("~~", "")
    value = re.sub(r"(?im)^\s*(?:#{1,6}\s+|>\s+|[-+•●▪]\s+|\d+[.)、]\s+)", "", value)
    value = re.sub(
        r"[\"']?assessed_at[\"']?\s*[:=：]?\s*[\"']?"
        r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?[\"']?",
        "", value, flags=re.I,
    )
    value = re.sub(rf"[\"']?(?:overall|status|explanation_status)[\"']?\s*[:=：]?\s*[\"']?{_STATES}[\"']?", "", value, flags=re.I)
    value = re.sub(r"\b(?:job_id|ID)\s*[:=：#]?\s*\d+\b", "", value, flags=re.I)
    value = re.sub(r"\b(?:source_fingerprint|rules_version)\s*[:=：]\s*[^\s,，;；]+", "", value, flags=re.I)
    value = re.sub(rf"(?<![\w]){_STATES}(?![\w])", "", value, flags=re.I)
    value = re.sub(r"\b(?:assessed_at|overall|job_id|source_fingerprint|rules_version|explanation_status)\b", "", value, flags=re.I)
    for field, label in (("match_score", "技能覆盖率"), ("matched_skills", "匹配技能"), ("missing_skills", "待补充技能")):
        value = re.sub(rf"\b{field}\b\s*[:=：]?\s*", label + "：", value, flags=re.I)
    value = re.sub(r"(?:https?://|javascript:|data:)[^\s<>()]+", "", value, flags=re.I)
    value = re.sub(r"\(\s*\)|（\s*）|\[\s*\]|\{\s*\}", "", value)
    lines = []
    for line in value.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip(" \t·|：:，,；;-")
        if line and not re.fullmatch(r"[_=\-]{3,}", line):
            lines.append(line)
    return "\n".join(lines)


def _unique_clean_reasons(reasons: list[str]) -> list[str]:
    # New scope/uncertainty metadata belongs in verified widgets, not AI prose.
    # Drop a mixed reason rather than showing stripped codes as broken text.
    cleaned = [clean_ai_text(reason) for reason in reasons if not _TRUST_METADATA.search(reason)]
    return list(dict.fromkeys(reason for reason in cleaned if reason))


def _legacy_reasons(lines: list[str]) -> list[str]:
    reasons: list[str] = []
    reason_section = False
    for raw in lines:
        if not raw.strip():
            reason_section = False
            continue
        control = raw.replace("*", "").replace("`", "")
        text = clean_ai_text(raw)
        if _QUALIFICATION.search(control):
            # A combined line may contain a clearly separated skill statement
            # before its qualification label. Keep only that explicit prefix.
            split = re.split(r"[。；;，,]\s*(?=资格|投递条件|待确认)", control, maxsplit=1)
            prefix = clean_ai_text(split[0]) if len(split) > 1 else ""
            if prefix and _REASON_START.search(prefix) and not _QUALIFICATION.search(prefix):
                reasons.append(prefix)
            reason_section = False
            continue
        if not text:
            continue
        if _REASON_START.search(text):
            reason_section = True
            text = re.sub(r"^(?:推荐理由|推荐原因|匹配理由|匹配亮点)\s*[:：]\s*", "", text)
            if text not in {"推荐理由", "推荐原因", "匹配理由", "匹配亮点"}:
                reasons.append(text)
        elif reason_section and re.match(r"^\s*(?:[-*+•]|\d+[.)、])\s+", raw):
            reasons.append(text)
        else:
            reason_section = False
    return _unique_clean_reasons(reasons)


def _unbound_section_heading(line: str) -> bool:
    """End a job section when a new heading cannot identify exactly one job."""

    stripped = line.strip()
    if re.match(r"\d+[.)、]\s*", stripped):
        return True  # An unlabeled numbered entry is never the previous job.
    if re.match(r"(?:[-*+]\s*)?(?:\*\*|__|`)?\s*(?:岗位\s*)?(?:ID|编号)\b", stripped, re.I):
        return True
    title = clean_ai_text(stripped).rstrip("：:")
    if title in {"推荐理由", "推荐原因", "匹配理由", "匹配亮点", "技能匹配", "技术匹配", "工作内容", "职责契合"}:
        return False
    if re.match(r"#{1,6}\s+", stripped):
        return True
    return bool(re.fullmatch(
        r"(?:[-*+]\s*)?(?:\*\*[^*]+\*\*|__[^_]+__)(?:\s*[（(][^）)]*[)）])?\s*", stripped
    ))


def build_job_reasons(response: AgentRecommendationResponse) -> dict[int, list[str]]:
    """Use structured reasons, or legacy sections with an explicit unique ID.

    Titles and positions in a list never determine which job gets an explanation.
    Older Streamlit session objects may not have the newly added attribute.
    """

    if getattr(response, "explanation_status", None) != "generated":
        return {}
    job_ids = [item.job.id for item in response.recommendations]
    structured = getattr(response, "job_explanations", [])
    if structured:
        if [item.job_id for item in structured] == job_ids:
            return {item.job_id: cleaned for item in structured
                    if (cleaned := _unique_clean_reasons(item.reasons))}
    text = getattr(response, "model_explanation", None)
    if not isinstance(text, str) or not text.strip():
        return {}
    sections: list[tuple[int, list[str]]] = []
    current: list[str] | None = None
    for line in text.splitlines():
        header = _JOB_HEADER.match(line)
        if header:
            tail = line[header.end():]
            if re.search(r"(?:ID|编号)\s*[:：#]?\s*\d+", tail, re.I) or re.match(
                r"\s*(?:[/、,&和与\-–—~至到]\s*\d|\.\d)", tail
            ):
                current = None  # Joint/ambiguous headings never name one job.
                continue
            current = []
            sections.append((int(header.group(1)), current))
        elif _unbound_section_heading(line):
            current = None
        elif current is not None:
            current.append(line)
    occurrences = Counter(job_id for job_id, _ in sections)
    associated = {
        job_id: _legacy_reasons(lines) for job_id, lines in sections
        if job_id in job_ids and occurrences[job_id] == 1
    }
    return {job_id: associated[job_id] for job_id in job_ids if associated.get(job_id)}
