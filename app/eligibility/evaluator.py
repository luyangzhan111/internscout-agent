"""Conservative, evidence-checked comparisons independent of skill scoring."""

from collections.abc import Sequence
import hashlib
import json
import re
from typing import Any

from app.eligibility.contracts import (
    ConditionCheck, ConditionRule, Dimension, EligibilityProfile, EvidenceSpan,
    JobEligibilityResult, UnknownReason,
)
from app.schemas.job_response import JobRead


RULES_VERSION = "stage23-rules-v1"
DIMENSIONS: tuple[Dimension, ...] = (
    "graduation_year", "degree", "experience", "city", "internship_duration"
)
_LABELS = {
    "graduation_year": "毕业届次", "degree": "学历", "experience": "工作经验",
    "city": "城市", "internship_duration": "可实习时长",
}
_DEGREES = ("below_associate", "associate", "bachelor", "master", "doctor")
_DEGREE_NAMES = dict(zip(_DEGREES, ("专科以下", "专科", "本科", "硕士", "博士")))
_STATUS_NAMES = {"enrolled": "在读", "completed": "已取得"}


def source_fingerprint(job: JobRead) -> str:
    """Identify the exact source snapshot used by the decision and citations."""

    snapshot = {name: getattr(job, name) for name in (
        "title", "description", "city", "status", "source", "source_url"
    )}
    snapshot["updated_at"] = job.updated_at.isoformat() if job.updated_at else None
    encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _valid_span(job: JobRead, span: EvidenceSpan) -> bool:
    value = getattr(job, span.field, None)
    return (
        span.field in {"title", "description", "city"}
        and isinstance(value, str)
        and type(span.start) is int and type(span.end) is int
        and 0 <= span.start < span.end <= len(value)
        and value[span.start:span.end] == span.text
    )


def _candidate_text(profile: EligibilityProfile, dimension: Dimension) -> str:
    if dimension == "graduation_year":
        return f"{profile.graduation_year} 届" if profile.graduation_year is not None else "未填写"
    if dimension == "degree":
        degree = _DEGREE_NAMES.get(profile.degree, "学历未填写")
        state = _STATUS_NAMES.get(profile.degree_status, "在读或取得情况未填写")
        return f"{degree}（{state}）"
    if dimension == "city":
        if profile.acceptable_cities is None:
            return "未填写"
        return "、".join(profile.acceptable_cities) if profile.acceptable_cities else "城市不限（已明确选择）"
    value = profile.work_experience_months if dimension == "experience" else profile.internship_months
    return f"{value} 个月" if value is not None else "未填写"


def _unrelated_values(rule: ConditionRule) -> bool:
    """Reject ambiguous rule shapes rather than silently ignoring their fields."""

    permitted = {
        "graduation_year": {"years"}, "degree": {"degrees", "degree_status"},
        "city": {"cities"}, "experience": {"min_months", "max_months"},
        "internship_duration": {"min_months", "max_months"},
    }[rule.dimension]
    return any(
        getattr(rule, name) not in (None, [])
        for name in {"years", "degrees", "degree_status", "cities", "min_months", "max_months"} - permitted
    )


def _constraint(rule: ConditionRule) -> set[Any] | tuple[float, float] | None:
    """Return comparable allowed values/bounds, or None for an invalid shape."""

    if _unrelated_values(rule):
        return None
    if rule.dimension == "graduation_year":
        if not rule.years or any(
            type(year) is not int or not 2000 <= year <= 2100 for year in rule.years
        ):
            return None
        if rule.operator == "in":
            return set(rule.years)
        if rule.operator == "min" and len(rule.years) == 1:
            return set(range(rule.years[0], 2101))
        return None
    if rule.dimension == "degree":
        if rule.operator == "any" and not rule.degrees and rule.degree_status is not None:
            return set(_DEGREES)
        if not rule.degrees or any(degree not in _DEGREES for degree in rule.degrees):
            return None
        if rule.operator == "min" and len(rule.degrees) == 1:
            return set(_DEGREES[_DEGREES.index(rule.degrees[0]):])
        if rule.operator == "max" and len(rule.degrees) == 1:
            return set(_DEGREES[:_DEGREES.index(rule.degrees[0]) + 1])
        if rule.operator == "in":
            return set(rule.degrees)
        return None
    if rule.dimension == "city":
        from app.eligibility.extractor import normalize_city
        if rule.operator != "in" or not rule.cities:
            return None
        cities = [normalize_city(city) for city in rule.cities]
        return set(cities) if all(cities) else None
    lower, upper = rule.min_months, rule.max_months
    if rule.operator == "min" and lower is not None and upper is None:
        return (lower, float("inf"))
    if rule.operator == "max" and upper is not None and lower is None:
        return (0, upper)
    if rule.operator == "range" and lower is not None and upper is not None and lower <= upper:
        return (lower, upper)
    return None


def _requirement_text(dimension: Dimension, allowed: Any, degree_status: str | None) -> str:
    if dimension == "graduation_year":
        return "毕业届次：" + "、".join(str(year) for year in sorted(allowed)) + " 届"
    if dimension == "degree":
        text = "学历：" + "、".join(_DEGREE_NAMES[degree] for degree in _DEGREES if degree in allowed)
        return text + (f"；须{_STATUS_NAMES[degree_status]}" if degree_status else "（原文未明确是否接受在读）")
    if dimension == "city":
        return "岗位城市：" + "、".join(sorted(allowed))
    lower, upper = allowed
    if upper == float("inf"):
        return f"至少 {lower:g} 个月"
    if lower == 0:
        return f"不超过 {upper:g} 个月"
    return f"{lower:g} 至 {upper:g} 个月（含边界）"


def _pending(check: ConditionCheck, category: UnknownReason, next_step: str) -> ConditionCheck:
    """Attach the cause at the decision branch, never infer it from display prose."""

    check.unknown_reason = category
    check.next_step = next_step
    return check


def _unsafe_degree_uncertainty(rules: list[ConditionRule]) -> bool:
    """Unknown alternatives/waivers cannot be treated as independent AND terms."""
    for rule in rules:
        text = "；".join(span.text for span in rule.evidence)
        if re.search(
            r"或者|或|[/／]|同等|等同|放宽|破格|豁免|例外|酌情|灵活|视情况|另议|面议|详谈|可替代"
            r"|不接受|不招|不考虑|不要求|不作要求|不做要求|不限定|不限制|不设(?:学历)?门槛|无学历门槛|不面向|不含|不包括|不适用|不属于|不得|不能|谢绝|勿投|无需|无须|非(?:本科|硕士|博士|必须|必需|硬性|强制)|\boptional\b"
            r"|\b(?:or|not|except|excluding|without|unless|equivalent|waiv\w*)\b", text, re.I,
        ):
            return True
        if (re.search(r"在读|在校|\benrolled\b|\bpursuing\b", text, re.I)
                and re.search(r"已取得|已获得|已毕业|持有|\b(?:completed|obtained|earned|hold(?:ing)?)\b", text, re.I)):
            return True
    return False


def _evaluate_degree(
    check: ConditionCheck, profile: EligibilityProfile, required: list[ConditionRule],
    uncertain: list[ConditionRule], allowed: set, state: str | None,
) -> ConditionCheck:
    """Compare level and state independently, retaining unresolved source scope."""
    level_required = any(rule.degrees for rule in required)
    if not level_required:
        check.requirement = f"学历状态：须{_STATUS_NAMES[state]}（原文未限定学历层级）"
    if uncertain and _unsafe_degree_uncertainty(uncertain):
        check.reason = "学历条件包含未明确的任选、放宽、否定或状态对应关系，需要进一步确认。"
        return _pending(check, "interpretation_uncertain", "请向招聘方确认学历条件各分支及在读状态的适用范围。")
    level_failure = level_required and profile.degree is not None and profile.degree not in allowed
    higher_unresolved = level_failure and all(
        not rule.degree_exclusive and rule.operator == "in"
        and (not rule.degrees or _DEGREES.index(profile.degree) > max(_DEGREES.index(degree) for degree in rule.degrees))
        for rule in required if rule.degrees
    )
    state_failure = state is not None and profile.degree_status is not None and profile.degree_status != state
    if (level_failure and not higher_unresolved) or state_failure:
        check.status = "not_met"
        check.reason = ("填写的学历层级不满足原文明确要求。" if level_failure and not higher_unresolved else
                        f"岗位明确要求{_STATUS_NAMES[state]}状态，填写的是{_STATUS_NAMES[profile.degree_status]}。")
        return check
    if higher_unresolved:
        check.reason = "填写的学历高于原文列出的层级，但原文未明确接受或排除更高学历，需要确认。"
        return _pending(check, "interpretation_uncertain", "请向招聘方确认是否接受所填的更高学历及其在读或取得状态。")
    if uncertain:
        check.reason = "明确学历条件尚未发现冲突，但其他学历表述仍无法可靠解析，需要进一步确认。"
        return _pending(check, "interpretation_uncertain", "请结合完整原文向招聘方确认未解析的学历条件。")
    if level_required and profile.degree is None:
        check.reason = "尚未填写学历层级，无法与岗位要求比较。"
        return _pending(check, "candidate_missing", "请补充你的学历层级，再重新核对条件。")
    if state is not None and profile.degree_status is None:
        check.reason = "岗位明确要求在读或已取得学历，尚未填写这一状态。"
        return _pending(check, "candidate_missing", "请补充该学历是在读还是已取得，再重新核对条件。")
    if state is None and profile.degree_status != "completed":
        check.reason = ("岗位未明确接受在读学历，需要确认在读是否满足该门槛。" if profile.degree_status == "enrolled"
                        else "尚未填写学历是在读还是已取得，不能据此认定已满足学历门槛。")
        category = "interpretation_uncertain" if profile.degree_status == "enrolled" else "candidate_missing"
        return _pending(check, category, "请向招聘方确认在读是否满足要求，或补充该学历的取得状态。")
    check.status = "met"
    check.reason = "填写的学历层级和原文明示的取得或在读状态符合已识别硬性条件。" if level_required else "填写的学历状态符合原文明示要求；学历层级未作推断。"
    return check


def _evaluate_dimension(
    job: JobRead, profile: EligibilityProfile, dimension: Dimension,
    rules: list[ConditionRule], malformed: bool = False,
) -> ConditionCheck:
    evidence: list[EvidenceSpan] = []
    seen: set[tuple] = set()
    notes: list[str] = []
    required: list[ConditionRule] = []
    unrestricted: list[ConditionRule] = []
    uncertain: list[ConditionRule] = []
    invalid = malformed
    for rule in rules:
        good_spans = [span for span in rule.evidence if _valid_span(job, span)]
        for span in good_spans:
            key = (span.field, span.start, span.end, span.text)
            if key not in seen:
                evidence.append(span)
                seen.add(key)
        valid_evidence = bool(rule.evidence) and len(good_spans) == len(rule.evidence)
        if rule.degree_scope == "conditional_capability":
            if not valid_evidence:
                invalid = True
            notes.append(
                "分学历能力说明，不作为共同学历门槛：" + "；".join(span.text for span in good_spans)
                + "；项目或研究能力仍需核对。" if valid_evidence else "分学历能力说明的原文依据无法核验。"
            )
            continue
        if rule.kind == "preferred":
            if not valid_evidence:
                invalid = True
            notes.append(
                "偏好条件，不作为拒绝依据：" + "；".join(span.text for span in good_spans)
                if valid_evidence else "偏好条件的原文依据无法核验，未用于判断。"
            )
            continue
        if not valid_evidence:
            invalid = True
        elif rule.kind == "uncertain":
            uncertain.append(rule)
            if rule.note:
                notes.append(rule.note)
        elif rule.kind == "unrestricted":
            unrestricted.append(rule)
        else:
            required.append(rule)

    check = ConditionCheck(
        dimension=dimension, status="unknown", candidate_value=_candidate_text(profile, dimension),
        requirement="；".join(span.text for span in evidence) or "未找到可核验的明确条件",
        reason="岗位原文未找到可明确比较的硬性条件。", evidence=evidence, notes=notes,
    )
    if invalid:
        check.reason = "条件或原文引用无法核验，不能据此作确定判断。"
        return _pending(check, "interpretation_uncertain", "打开岗位来源核对完整原文；必要时更新岗位信息后重新判断。")
    if uncertain and dimension != "degree":
        check.reason = "原文存在含糊或当前无法可靠解析的条件，需要进一步确认。"
        return _pending(check, "interpretation_uncertain", f"请结合完整原文向招聘方确认{_LABELS[dimension]}的具体要求。")
    if unrestricted:
        if required or any(
            rule.operator != "any" or any(getattr(rule, field) not in (None, []) for field in (
                "years", "degrees", "degree_status", "cities", "min_months", "max_months"
            )) for rule in unrestricted
        ):
            check.reason = "原文的不限要求与其他条件矛盾，或规则本身无效，需要确认。"
            if required:
                return _pending(check, "requirements_conflict", f"请向招聘方确认{_LABELS[dimension]}以“不限”还是其他限制为准。")
            return _pending(check, "interpretation_uncertain", f"请核对原文中{_LABELS[dimension]}“不限”的适用范围，必要时向招聘方确认。")
        if uncertain:
            check.reason = "原文同时包含不限与尚无法解析的学历说明，需要进一步确认。"
            return _pending(check, "interpretation_uncertain", "请向招聘方核实学历不限的适用范围及其余学历说明。")
        check.status = "met"
        check.reason = f"原文明示{_LABELS[dimension]}不限，这一项没有额外门槛。"
        check.requirement = f"{_LABELS[dimension]}不限（原文明示）"
        return check
    if not required:
        if uncertain:
            check.reason = "原文存在含糊或当前无法可靠解析的条件，需要进一步确认。"
            return _pending(check, "interpretation_uncertain", f"请结合完整原文向招聘方确认{_LABELS[dimension]}的具体要求。")
        if notes:
            check.reason = "原文只识别到偏好，未找到可确定比较的硬性条件。"
        return _pending(check, "source_unspecified", f"岗位原文未明确{_LABELS[dimension]}的硬性要求，请查看完整招聘信息或向招聘方确认。")

    constraints = [_constraint(rule) for rule in required]
    if any(value is None for value in constraints):
        check.reason = "条件的范围、单位或城市无法可靠比较，需要确认。"
        return _pending(check, "interpretation_uncertain", f"请核对{_LABELS[dimension]}的范围、单位或名称，必要时向招聘方确认。")
    degree_states = {rule.degree_status for rule in required if rule.degree_status is not None}
    if dimension in {"experience", "internship_duration"}:
        allowed = (max(value[0] for value in constraints), min(value[1] for value in constraints))
        conflict = allowed[0] > allowed[1]
    else:
        allowed = set.intersection(*constraints)
        conflict = not allowed
    if conflict or len(degree_states) > 1:
        check.reason = "岗位原文中同一项条件互相冲突，需要招聘方确认。"
        return _pending(check, "requirements_conflict", f"请向招聘方核实相互冲突的{_LABELS[dimension]}要求，以确认后的条件为准。")
    degree_state = next(iter(degree_states), None)
    check.requirement = _requirement_text(dimension, allowed, degree_state)

    if dimension == "degree":
        return _evaluate_degree(check, profile, required, uncertain, allowed, degree_state)
    if dimension == "graduation_year" and all(rule.operator == "min" for rule in required):
        check.requirement = f"毕业届次：{min(allowed)}届及以后（含当届）"

    if dimension == "graduation_year":
        candidate = profile.graduation_year
    elif dimension == "degree":
        candidate = profile.degree
    elif dimension == "experience":
        candidate = profile.work_experience_months
    elif dimension == "internship_duration":
        candidate = profile.internship_months
    else:
        candidate = profile.acceptable_cities
    if candidate is None:
        check.reason = f"尚未填写{_LABELS[dimension]}，无法与岗位要求比较。"
        return _pending(check, "candidate_missing", f"请补充你的{_LABELS[dimension]}，再重新核对条件。")

    if dimension == "city":
        from app.eligibility.extractor import normalize_city
        candidate_cities = [normalize_city(city) for city in candidate]
        if candidate and not all(candidate_cities):
            check.reason = "部分意向城市无法可靠识别，请确认城市名称。"
            return _pending(check, "interpretation_uncertain", "请核对已填写的意向城市名称，使用明确的城市名称后重新判断。")
        matches = not candidate or bool(set(candidate_cities) & allowed)
    elif dimension in {"experience", "internship_duration"}:
        if dimension == "internship_duration" and candidate > allowed[1]:
            check.reason = "填写的可实习时长超过岗位期限上界，需要确认能否按岗位期限安排。"
            return _pending(check, "interpretation_uncertain", "请确认你能否按岗位期限缩短实习安排，并向招聘方核实是否接受。")
        matches = allowed[0] <= candidate <= allowed[1]
    else:
        matches = candidate in allowed
    check.status = "met" if matches else "not_met"
    check.reason = (
        f"填写的{_LABELS[dimension]}符合原文中已识别的硬性条件。"
        if matches else f"填写的{_LABELS[dimension]}不符合原文中已识别的硬性条件。"
    )
    return check


def evaluate_rules(
    job: JobRead, profile: EligibilityProfile, rules: Sequence[ConditionRule],
) -> JobEligibilityResult:
    """Compare extracted rules, revalidating their shapes and source citations."""

    by_dimension: dict[Dimension, list[ConditionRule]] = {dimension: [] for dimension in DIMENSIONS}
    malformed: set[Dimension] = set()
    for rule in rules:
        try:
            validated = ConditionRule.model_validate(rule.model_dump())
        except (ValueError, TypeError, AttributeError):
            dimension = getattr(rule, "dimension", None)
            malformed.update([dimension] if dimension in DIMENSIONS else DIMENSIONS)
            continue
        by_dimension[validated.dimension].append(validated)
    checks = [_evaluate_dimension(job, profile, dimension, by_dimension[dimension], dimension in malformed)
              for dimension in DIMENSIONS]
    from app.eligibility.work_location import evaluate_work_location
    checks = [evaluate_work_location(job, profile, check) if check.dimension == "city" else check
              for check in checks]
    blocking = [f"{_LABELS[check.dimension]}：{check.reason}" for check in checks if check.status == "not_met"]
    if job.status == "closed":
        blocking.insert(0, "岗位已标记关闭，当前不可作为可投岗位。")
    if job.status == "closed":
        overall, reason = "not_met", "岗位已标记关闭，当前不可投递。"
    elif blocking:
        overall, reason = "not_met", "至少一项明确投递条件不满足。"
    elif any(check.status == "unknown" for check in checks):
        overall, reason = "unknown", "部分条件尚待确认，暂不能判断五项条件全部符合。"
    else:
        overall, reason = "met", "五项已识别条件均符合；其他招聘要求仍需核对岗位原文。"
    return JobEligibilityResult(
        job=job, overall=overall, reason=reason, checks=checks, blocking_reasons=blocking,
        source_fingerprint=source_fingerprint(job), rules_version=RULES_VERSION,
    )


def evaluate_eligibility(job: JobRead, profile: EligibilityProfile) -> JobEligibilityResult:
    from app.eligibility.extractor import extract_conditions
    return evaluate_rules(job, profile, extract_conditions(job))
