"""Evidence-bound work arrangements refine the geographic check only.

The structured city remains an office location, not proof that remote work from
another city is allowed.  No work-arrangement signal means an exact no-op.
"""

from dataclasses import dataclass
import re

from app.eligibility.contracts import ConditionCheck, EligibilityProfile, EvidenceSpan
from app.eligibility.extractor import _CITY_ALIASES, extract_conditions, normalize_city
from app.schemas.job_response import JobRead


_HYBRID = re.compile(
    r"线上\s*(?:和|与|/|／|、)?\s*线下\s*(?:相)?结合|线下\s*(?:和|与|/|／|、)?\s*线上\s*(?:相)?结合"
    r"|混合(?:办公|工作|实习)|\bhybrid\s+(?:work(?:ing)?|internship)\b", re.I,
)
_REMOTE = re.compile(
    r"(?:(?:支持|允许|接受|可以|可)(?:全|完全)?(?:异地)?(?:全)?(?:远程|线上)(?:办公|工作|实习)?"
    r"|(?:全|完全)远程(?:办公|工作|实习)?|(?:远程|线上)(?:办公|工作|实习)"
    r"|(?:远程|线上)(?:办公|工作|实习)?\s*(?:仅限|限于|限在|限定在|范围)"
    r"|(?<!不)(?:仅限|限于|只接受|仅接受|仅面向|只支持|仅支持)[^。；;\n]{1,30}(?:远程(?:办公|工作|实习)?|线上(?:办公|工作|实习))"
    r"|\b(?:fully\s+remote|remote\s+(?:work(?:ing)?|internship))\b)", re.I,
)
_FULL_REMOTE = re.compile(r"(?:全|完全)远程|\bfully\s+remote\b", re.I)
_NAMED_CITY = "(?:" + "|".join(re.escape(city) for city in sorted(_CITY_ALIASES, key=len, reverse=True)) + ")"
_NO_REMOTE = re.compile(
    r"(?:不支持|不接受|不允许|不提供|不能|不得|禁止|无法)(?:在)?"
    rf"(?:(?:全|完全|全国|中国境内|中国大陆|全球|世界各地|异地|跨城|{_NAMED_CITY})"
    r"(?:范围(?:内)?)?(?:的)?)?"
    r"(?:远程|线上)(?:办公|工作|实习)?"
    r"|\b(?:no\s+remote|remote\s+(?:work\s+)?(?:is\s+)?not\s+(?:allowed|supported))\b", re.I,
)
_NO_CROSS_CITY = re.compile(
    r"(?:不支持|不接受|不允许|不能|不得|禁止)(?:异地|跨城)(?:远程|线上)?"
    r"|(?:远程|线上)(?:办公|工作|实习)?(?:也)?(?:必须|须|需)(?:在)?(?:本地|当地|同城)"
)
_NO_FULL_REMOTE = re.compile(r"(?:不支持|不接受|不允许|不能|不得|禁止)(?:全|完全)远程(?:办公|工作|实习)?")
_MUST_ONSITE = re.compile(
    r"(?:必须|须|需要|需|要求|只能|仅可|全程)[^。；;\n，,]{0,12}(?:到岗|线下办公|现场办公|线下实习|现场实习)"
    r"|(?:工作|办公|实习)(?:形式|方式|模式)\s*[:：为是]\s*(?:线下|现场)"
    r"|\b(?:must\s+(?:work\s+)?on[ -]?site|on[ -]?site\s+required)\b", re.I,
)
_OPTION = re.compile(r"(?:可选|任选|二选一|选择|或者|或|\bor\b)", re.I)
_CROSS_CITY = re.compile(r"异地|跨城|全国|中国境内|中国大陆|全球|世界各地|anywhere", re.I)
_UNLIMITED = re.compile(
    r"(?:城市|地点|地域|地区|位置)\s*[:：]?\s*不限|不限(?:城市|地点|地域|地区|位置)"
    r"|全球|世界各地|\b(?:anywhere|any\s+(?:city|location))\b", re.I,
)
_NATIONAL = re.compile(r"全国|中国境内|中国大陆|\bmainland\s+china\b", re.I)
_GEOGRAPHIC_SCOPE = (
    r"(?:全国|中国境内|中国大陆|全球|世界各地|异地|跨城|mainland\s+china|anywhere|any\s+(?:city|location)"
    r"|(?:城市|地点|地域|地区|位置)\s*[:：]?\s*不限|不限(?:城市|地点|地域|地区|位置))"
)
_REMOTE_MODE = r"(?:(?:全|完全)?(?:远程|线上)(?:办公|工作|实习)?|(?:fully\s+)?remote\s+(?:work(?:ing)?|internship))"
_BOUND_REMOTE_SCOPE = re.compile(
    rf"(?P<before>{_GEOGRAPHIC_SCOPE})\s*(?:范围(?:内)?|的)?\s*(?:异地|跨城)?{_REMOTE_MODE}"
    rf"|{_REMOTE_MODE}\s*(?:(?:地域|地区|城市|范围)\s*[:：]?\s*)?"
    rf"(?:(?:支持|允许|可在|可以在|from|within|in)\s*)?(?P<after>{_GEOGRAPHIC_SCOPE})", re.I,
)
_EXPLICIT_SCOPE = re.compile(
    rf"(?:工作地点|办公地点|工作地域|远程(?:办公|工作|实习)?(?:地域|地区|城市|范围)|地域|地区|城市|地点|范围)"
    rf"\s*[:：]?\s*{_GEOGRAPHIC_SCOPE}\s*"
    r"|(?:工作|办公)?(?:城市|地点|地域|地区|位置)\s*[:：]?\s*不限"
    r"|不限(?:工作|办公)?(?:城市|地点|地域|地区|位置)", re.I,
)
_REMOTE_LIMIT = re.compile(
    r"(?:远程|线上)(?:办公|工作|实习)?\s*[（(，,]?\s*(?:地域|地区|城市|范围)?\s*[:：]?\s*"
    r"(?:仅限|限于|限在|限定在|只限|限|必须(?:居住)?在|须(?:居住)?在|需(?:居住)?在)\s*(?P<after>[^，,。；;\n]+)"
    r"|(?:仅限|限于|只接受|仅接受|仅面向|只支持|仅支持)\s*(?P<before>[^，,。；;\n]+?)(?:异地)?(?:远程|线上)(?:办公|工作|实习)?", re.I,
)
_PERMITTED_CITIES = re.compile(
    r"(?<!不)(?:支持|允许|接受|可在|可以在)\s*(?P<area>[^，,。；;\n]{1,35}?)(?:异地)?(?:远程|线上)(?:办公|工作|实习)", re.I,
)
_ONSITE_CITY = re.compile(
    r"(?:必须|须|需要|需|要求)(?:在|于)\s*(?P<area>[^，,。；;\n]{1,25}?)(?:到岗|线下办公|现场办公|线下实习|现场实习)"
    r"|(?:必须|须|需要|需|要求)[^，,。；;\n]{0,12}?(?:到|赴|前往|在|于)\s*"
    r"(?P<travel_area>[^，,。；;\n]{1,15}?)(?:办公|实习|工作)"
)
_ALTERNATIVE = re.compile(
    r"(?P<onsite>[^，,。；;\n：:]{1,25}?)(?:线下(?:办公|工作|实习)?|到岗(?:办公|工作|实习)?)\s*(?:或(?:者)?|/|／|\bor\b)\s*"
    r"(?P<remote>[^，,。；;\n]{1,25}?)(?:异地)?(?:远程|线上)(?:办公|工作|实习)?", re.I,
)
_REVERSE_ALTERNATIVE = re.compile(
    r"(?P<remote>[^，,。；;\n：:]{1,25}?)(?:异地)?(?:远程|线上)(?:办公|工作|实习)?\s*(?:或(?:者)?|/|／|\bor\b)\s*"
    r"(?P<onsite>[^，,。；;\n]{1,25}?)(?:线下(?:办公|工作|实习)?|到岗(?:办公|工作|实习)?)", re.I,
)


@dataclass(frozen=True)
class _Signal:
    evidence: EvidenceSpan
    hybrid: bool
    remote: bool
    full_remote: bool
    no_remote: bool
    no_cross_city: bool
    onsite: bool
    alternative: bool


def _spans(job: JobRead):
    for field in ("title", "description"):
        source = getattr(job, field) or ""
        for match in re.finditer(r"[^。；;\n!?！？]+", source):
            start, end = match.span()
            while start < end and source[start].isspace():
                start += 1
            while end > start and source[end - 1].isspace():
                end -= 1
            if start < end:
                yield EvidenceSpan(field=field, text=source[start:end], start=start, end=end)


def _job_mode_match(pattern: re.Pattern, text: str) -> bool:
    """Do not promote tools, duties, past experience or team descriptions."""
    for match in pattern.finditer(text):
        prefix, suffix = text[:match.start()], text[match.end():]
        if re.match(r"\s*(?:的)?(?:相关)?(?:经验|经历|能力|工具|功能|系统|平台|数据|团队|活动|课程|会议|培训|部署|调试|访问|控制|解决方案|需求|\b(?:experience|team|tool|event|deployment)\b)", suffix, re.I):
            continue
        local_prefix = re.split(r"[，,：:]", prefix)[-1]
        if re.search(r"(?:组织|举办|策划|开展|运营|参加|参与|负责)[^，,]{0,12}$", local_prefix) and re.search(
            r"活动|会议|课程|培训|展会|部署|数据|业务|服务|渠道|场景", suffix,
        ):
            continue
        if re.search(r"(?:具备|拥有|熟悉|了解|有)[^，,]{0,8}$", local_prefix) and re.search(r"经验|经历|能力", suffix):
            continue
        return True
    return False


def _bound_remote_scope(text: str) -> str:
    """Use geographic terms only when they qualify this job's remote permission.

    Customer/team/market coverage in another comma clause is not an applicant
    location range. An explicit workplace/range label can qualify a preceding
    remote mode without requiring both statements in one comma clause.
    """
    positive = _NO_CROSS_CITY.sub("", _NO_REMOTE.sub("", text))
    if not _job_mode_match(_REMOTE, positive):
        return ""
    scopes = []
    for part in re.split(r"[，,]", positive):
        if _job_mode_match(_REMOTE, part):
            scopes.extend(match["before"] or match["after"]
                          for match in _BOUND_REMOTE_SCOPE.finditer(part))
        if _EXPLICIT_SCOPE.fullmatch(part.strip()):
            scopes.append(part)
    return "；".join(scopes)


def _signals(job: JobRead) -> list[_Signal]:
    result = []
    for span in _spans(job):
        text = span.text
        hybrid = _job_mode_match(_HYBRID, text)
        no_full_remote = _job_mode_match(_NO_FULL_REMOTE, text)
        no_remote = _job_mode_match(_NO_REMOTE, _NO_CROSS_CITY.sub("", _NO_FULL_REMOTE.sub("", text)))
        no_cross_city = _job_mode_match(_NO_CROSS_CITY, text)
        # Remove denials before looking for positive permission.
        positive = _NO_CROSS_CITY.sub("", _NO_REMOTE.sub("", text))
        remote = _job_mode_match(_REMOTE, positive)
        full_remote = remote and bool(_FULL_REMOTE.search(positive))
        onsite = _job_mode_match(_MUST_ONSITE, text) or _job_mode_match(_ONSITE_CITY, text) or no_full_remote
        alternative = bool(_ALTERNATIVE.search(text) or _REVERSE_ALTERNATIVE.search(text)) or (
            bool(_OPTION.search(text)) and bool(re.search(r"到岗|线下|现场", text)) and remote
            and not bool(re.search(r"每周|每月|定期|至少|必须", text))
        )
        if hybrid or remote or no_remote or no_cross_city or onsite:
            result.append(_Signal(span, hybrid, remote, full_remote, no_remote, no_cross_city, onsite, alternative))
    return result


def _city_list(text: str) -> set[str] | None:
    text = re.sub(r"^(?:工作地点|办公地点|地点|城市)\s*[:：]?\s*", "", text.strip())
    text = re.sub(r"^(?:支持|允许|接受|可选择|可选|可以|可|必须在|须在|必须|在|于|居住在|居住于|位于)\s*", "", text)
    text = text.strip(" ：:。.（）() ")
    text = re.sub(r"(?:的候选人|候选人|居民|地区|区域|本地|当地)\s*$", "", text).strip()
    parts = re.split(r"[、,，/／|]|或者|或|和|与|及|\s+(?:or|and)\s+", text, flags=re.I)
    cities = [normalize_city(part.strip()) for part in parts]
    return set(cities) if cities and all(cities) else None


def _venue(job: JobRead) -> tuple[set[str] | None, bool, bool]:
    """Reuse only source-backed city constraints already understood by the extractor."""
    rules = [rule for rule in extract_conditions(job) if rule.dimension == "city"]
    required = [set(rule.cities) for rule in rules if rule.kind == "required" and rule.operator == "in"]
    unrestricted = any(rule.kind == "unrestricted" for rule in rules)
    unknown = False
    for rule in rules:
        if rule.kind != "uncertain":
            continue
        for span in rule.evidence:
            if span.field == "city":
                unknown = True
            label = re.search(r"工作(?:地点|城市)|办公地点|职位地点|\b(?:work\s+)?location\b", span.text, re.I)
            if label:
                area = span.text[label.end():].lstrip(" ：:")
                area = re.split(r"线上线下|混合办公|远程|线上|线下|到岗|现场", area, maxsplit=1)[0]
                unknown |= not bool(_city_list(area.strip(" （(")))
    if not required:
        return None, False, unknown
    allowed = set.intersection(*required)
    return allowed or None, not allowed or unrestricted, unknown


def _current_evidence(job: JobRead, baseline: ConditionCheck, signals: list[_Signal]) -> list[EvidenceSpan]:
    result = []
    seen = set()
    source_cities = [span for rule in extract_conditions(job) if rule.dimension == "city"
                     and rule.kind in {"required", "unrestricted"} for span in rule.evidence]
    for span in [*baseline.evidence, *source_cities, *(signal.evidence for signal in signals)]:
        source = getattr(job, span.field) or ""
        key = (span.field, span.start, span.end, span.text)
        if key not in seen and source[span.start:span.end] == span.text:
            result.append(span)
            seen.add(key)
    return result


def evaluate_work_location(
    job: JobRead, profile: EligibilityProfile, baseline_city_check: ConditionCheck,
) -> ConditionCheck:
    """Refine only city eligibility without asserting attendance or legal eligibility."""
    signals = _signals(job)
    if not signals:
        return baseline_city_check
    check = baseline_city_check.model_copy(deep=True)
    check.evidence = _current_evidence(job, check, signals)
    check.notes.append("本项只核对地理范围；到岗频次、搬迁安排及签证/工作许可未据此认定满足。")
    check.requirement += "；工作形式：" + "；".join(dict.fromkeys(signal.evidence.text for signal in signals))

    def pending(reason: str, *, conflict: bool = False, candidate: bool = False) -> ConditionCheck:
        check.status = "unknown"
        check.reason = reason
        check.unknown_reason = "requirements_conflict" if conflict else "candidate_missing" if candidate else "interpretation_uncertain"
        check.next_step = ("请补充意向城市，再按岗位明确的工作地域核对。" if candidate else
                           "请向招聘方确认适用的办公形式、允许异地的城市/地域及必须到岗的地点和频次。")
        return check

    def resolved(allowed: set[str] | None, reason: str) -> ConditionCheck:
        candidate = profile.acceptable_cities
        if candidate is None:
            return pending("尚未填写意向城市，无法核对岗位允许的工作地域。", candidate=True)
        cities = [normalize_city(city) for city in candidate]
        if candidate and not all(cities):
            return pending("部分意向城市无法可靠识别，不能据此认定满足岗位地域范围。")
        check.status = "met" if not candidate or allowed is None or bool(set(cities) & allowed) else "not_met"
        check.reason = reason if check.status == "met" else "填写的意向城市不在原文明示的到岗或远程工作地域范围内。"
        check.unknown_reason = None
        check.next_step = ""
        return check

    alternatives = []
    limits = []
    onsite_limits = []
    scope_unknown = False
    unrestricted_remote = False
    national_remote = False
    cross_permission = False
    for signal in signals:
        text = signal.evidence.text
        for match in [match for pattern in (_ALTERNATIVE, _REVERSE_ALTERNATIVE) for match in pattern.finditer(text)]:
            left, right = _city_list(match["onsite"]), _city_list(match["remote"])
            if left and right:
                alternatives.append(left | right)
            elif left and _NATIONAL.fullmatch(match["remote"].strip()):
                national_remote = True
                alternatives.append(left)
            elif left and _UNLIMITED.fullmatch(match["remote"].strip()):
                unrestricted_remote = True
                alternatives.append(left)
            else:
                scope_unknown = True
        for match in _ONSITE_CITY.finditer(text):
            cities = _city_list(match["area"] or match["travel_area"])
            if cities:
                onsite_limits.append(cities)
            else:
                scope_unknown = True
        if not (signal.remote or signal.hybrid):
            continue
        for match in re.finditer(r"(?:仅限|限于|限定在|限定于)\s*([^，,。；;\n]+)", text):
            prefix = re.split(r"[，,]", text[:match.start()])[-1].strip()
            if prefix and not (
                _job_mode_match(_REMOTE, prefix) or _job_mode_match(_HYBRID, prefix)
                or re.fullmatch(r"(?:本岗位|本职位|工作|办公|实习|远程)?(?:地域|地区|城市|地点|范围)?\s*[:：]?", prefix)
            ):
                continue
            area = re.split(r"(?:远程|线上|线下)(?:办公|工作|实习)?", match[1], maxsplit=1)[0]
            cities = _city_list(area)
            if cities:
                limits.append(cities)
        bound_scope = _bound_remote_scope(text)
        cross_permission |= signal.remote and bool(_CROSS_CITY.search(bound_scope))
        unrestricted_remote |= signal.remote and bool(_UNLIMITED.search(bound_scope))
        national_remote |= signal.remote and bool(_NATIONAL.search(bound_scope))
        for match in _REMOTE_LIMIT.finditer(text):
            area = match["after"] or match["before"]
            if _NATIONAL.fullmatch(area.strip()):
                national_remote = True
            elif _UNLIMITED.fullmatch(area.strip()):
                unrestricted_remote = True
            else:
                cities = _city_list(area)
                if cities:
                    limits.append(cities)
                else:
                    scope_unknown = True
        if re.search(r"\b(?:within|residents?|based\s+in)\b", text, re.I):
            scope_unknown = True
        for match in _PERMITTED_CITIES.finditer(text):
            area = match["area"]
            if area in {"异地", "跨城", "全", "完全", "全国", "中国境内", "中国大陆", "全球"}:
                continue
            cities = _city_list(area)
            if cities:
                limits.append(cities)
                cross_permission = True

    has_remote = any(signal.remote for signal in signals)
    has_hybrid = any(signal.hybrid for signal in signals)
    denial = any(signal.no_remote for signal in signals)
    no_cross_city = any(signal.no_cross_city for signal in signals)
    onsite = any(signal.onsite and not signal.alternative for signal in signals)
    if ((denial and (has_remote or has_hybrid)) or (no_cross_city and cross_permission)
            or (onsite and any(signal.full_remote and not signal.alternative for signal in signals))):
        return pending("原文同时给出相互矛盾的远程/到岗要求，不能据此确定可工作的地域。", conflict=True)
    venue, venue_conflict, venue_unknown = _venue(job)
    if onsite_limits:
        values = [*onsite_limits, *([venue] if venue else [])]
        venue = set.intersection(*values)
        venue_conflict |= not bool(venue)
    if venue_conflict and not alternatives and not (limits or unrestricted_remote or national_remote):
        return pending("岗位明确地点要求相互冲突，需要确认适用地点。", conflict=True)
    if onsite or denial or no_cross_city:
        if venue_unknown:
            return pending("岗位要求到岗或同城工作，但明确地点中仍有无法可靠识别的地域。")
        if limits:
            required_places = [*limits, *([venue] if venue else [])]
            venue = set.intersection(*required_places)
            venue_conflict |= not bool(venue)
        if venue_conflict:
            return pending("必须到岗的地点与岗位其他地点要求相互冲突。", conflict=True)
        if venue is None:
            return pending("岗位要求到岗或不允许异地远程，但未找到可可靠比较的具体城市。")
        return resolved(venue, "填写的意向城市符合原文明示的到岗/同城要求；出勤安排仍需另行核实。")
    if scope_unknown:
        return pending("岗位远程或可选地点的地域范围尚不能可靠识别，不能推断为全球或任意城市可工作。")
    if limits:
        remote_cities = set.intersection(*limits)
        if not remote_cities:
            return pending("原文的远程地域限制相互冲突，需要确认实际适用范围。", conflict=True)
        if unrestricted_remote:
            return pending("原文同时给出不限地域与明确远程地域限制，需要确认实际适用范围。", conflict=True)
        allowed = remote_cities | (set.union(*alternatives) if alternatives else set())
        return resolved(allowed, "填写的意向城市符合原文明示的远程或可选工作地点范围；其他办公安排仍需核实。")
    if alternatives and not (unrestricted_remote or national_remote):
        return resolved(set.union(*alternatives), "填写的意向城市符合原文明示的可选到岗/远程地点之一。")
    if unrestricted_remote and has_remote:
        check.status = "met"
        check.reason = "原文明示允许不限城市/地域的远程工作；本项仅确认地理限制已放宽。"
        check.unknown_reason = None
        check.next_step = ""
        return check
    if national_remote and has_remote:
        candidate = profile.acceptable_cities
        if candidate is not None:
            cities = [normalize_city(city) for city in candidate]
            if cities and (not all(cities) or any(city in {"香港", "澳门", "台北"} for city in cities)):
                return pending("原文明示国内/大陆远程范围，填写的城市与这一地域范围尚不能可靠比较。")
        return resolved(None, "填写的意向城市在原文明示的国内/大陆远程范围内；工作许可和其他办公安排仍需核实。")
    # An office-city match remains useful geographic evidence, but never proves
    # that the applicant can meet the hybrid attendance schedule.
    if venue_unknown:
        return pending("岗位城市或明确工作地点仍含无法可靠识别的地域，不能以办公形式推断已经符合。")
    if profile.acceptable_cities is None:
        return pending("岗位包含混合/远程工作形式，尚未填写意向城市，无法核对地理范围。", candidate=True)
    cities = [normalize_city(city) for city in profile.acceptable_cities]
    if profile.acceptable_cities and not all(cities):
        return pending("部分意向城市无法可靠识别，且岗位未明确异地工作范围，需要确认。")
    if venue and (not profile.acceptable_cities or bool(set(cities) & venue)):
        return resolved(venue, "填写的意向城市与明确岗位城市相符或已明确城市不限；混合/远程模式的实际安排尚未额外核实。")
    return pending("岗位采用混合/远程工作形式，但未明确允许异地的地域范围，不能仅按结构化城市硬性拒绝。")
