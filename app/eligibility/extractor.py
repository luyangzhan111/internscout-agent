"""Conservative, evidence-preserving rules for five application conditions.

This deliberately has no model, provider calls, or approximate date inference.
Unsupported clauses stay visible as uncertain instead of becoming hard filters.
"""

from collections.abc import Iterator
import re

from app.eligibility.contracts import ConditionRule, EvidenceSpan
from app.schemas.job_response import JobRead


_CITY_NAMES = {
    "北京": "beijing", "上海": "shanghai", "深圳": "shenzhen",
    "广州": "guangzhou", "天津": "tianjin", "重庆": "chongqing",
    "杭州": "hangzhou", "南京": "nanjing", "苏州": "suzhou",
    "成都": "chengdu", "武汉": "wuhan", "西安": "xian",
    "长沙": "changsha", "合肥": "hefei", "郑州": "zhengzhou",
    "济南": "jinan", "青岛": "qingdao", "大连": "dalian",
    "沈阳": "shenyang", "厦门": "xiamen", "福州": "fuzhou",
    "东莞": "dongguan", "佛山": "foshan", "珠海": "zhuhai",
    "惠州": "huizhou", "无锡": "wuxi", "宁波": "ningbo",
    "南昌": "nanchang", "昆明": "kunming", "南宁": "nanning",
    "贵阳": "guiyang", "石家庄": "shijiazhuang", "太原": "taiyuan",
    "长春": "changchun", "哈尔滨": "harbin", "海口": "haikou",
    "兰州": "lanzhou", "银川": "yinchuan", "乌鲁木齐": "urumqi",
    "香港": "hong kong", "澳门": "macau", "台北": "taipei",
}
_CITY_ALIASES = {
    alias.casefold(): name
    for name, english in _CITY_NAMES.items()
    for alias in (name, name + "市", english)
}
_CITY_ALIASES.update({"xi'an": "西安", "xi’an": "西安", "hongkong": "香港"})
_DEGREES = (
    (r"博士|\b(?:ph\.?d\.?|doctorate|doctoral)(?:\s+degree)?\b", "doctor"),
    (r"硕士|\bmaster(?:['’]s)?(?:\s+degree)?\b", "master"),
    (r"本科|学士|\bbachelor(?:['’]s)?(?:\s+degree)?\b", "bachelor"),
    (r"大专|专科|\bassociate(?:['’]s)?(?:\s+degree)?\b", "associate"),
    (r"高中|中专|职高|\bhigh\s+school\b", "below_associate"),
)
_RANK = {degree: rank for rank, degree in enumerate(
    ("below_associate", "associate", "bachelor", "master", "doctor")
)}
_PREFERRED = re.compile(r"优先|加分|更佳|最好|优选|\bpreferred\b|\ba\s+plus\b|\bdesirable\b", re.I)
_GRADUATION = re.compile(r"届|毕业|应届|\bgraduat(?:e[sd]?|ion|ing)\b|\bclass\s+of\b", re.I)
_DEGREE_CONTEXT = re.compile(r"学历|学位|在读|在校|本科|硕士|博士|研究生|硕博|大专|专科|学士|高中|中专|\bdegree\b|\bbachelor|\bmaster|\bph\.?d|\benrolled\b|\bpostgrad|\bpostdoc", re.I)
_EXPERIENCE = re.compile(r"经验|\bexperience\b", re.I)
_INTERNSHIP = re.compile(r"实习|\bintern(?:ship)?\b", re.I)
_CITY_LABEL = re.compile(r"工作(?:地点|城市)|办公地点|职位地点|\b(?:work\s+)?location\b|(?<![A-Za-z])base(?:d)?(?:\s+in)?(?=\s|[:：]|[\u4e00-\u9fff]|$)", re.I)
_NEGATIVE = re.compile(r"不接受|不招|不考虑|不要求|不面向|不含|不包含|不适用|不属于|不得|不能|谢绝|勿投|无需|非(?:应届|20\d{2}|本科|硕士|博士)|排除|除外|不包括|\b(?:not|except|excluding|without)\b", re.I)
_NUMBER = r"(?:\d+(?:\.\d+)?|[零一二两三四五六七八九十]+|半)"
_UNIT = r"(?:个?月|年|months?|years?)"
_DURATION = re.compile(rf"(?P<number>{_NUMBER})\s*\+?\s*(?P<unit>{_UNIT})", re.I)
_RANGE = re.compile(rf"(?P<first>{_NUMBER})\s*(?P<unit1>{_UNIT})?\s*(?:[-–—~～至到]|\bto\b)\s*(?P<second>{_NUMBER})\s*(?P<unit2>{_UNIT})", re.I)


def normalize_city(value: str) -> str | None:
    """Canonicalize only explicitly supported city names and aliases."""

    return _CITY_ALIASES.get(" ".join(value.strip().split()).casefold())


def _span(field: str, text: str, start: int, end: int) -> EvidenceSpan:
    return EvidenceSpan(field=field, text=text[start:end], start=start, end=end)


def _clauses(text: str) -> Iterator[tuple[int, int]]:
    """Split clauses without breaking year/degree/city enumerations."""

    start = 0
    for match in re.finditer(r"[。；;\n!?！？，,（）()]", text):
        delimiter = match.group()
        if delimiter in ",，":
            left = text[start:match.start()].rstrip()
            right = text[match.end():].lstrip()
            if re.search(r"20\d{2}$", left) and re.match(r"20\d{2}", right):
                continue
            if not _PREFERRED.search(re.split(r"[，,。；;\n]", right, maxsplit=1)[0]) and any(re.search("(?:" + pattern + r")$", left, re.I) and
                   any(re.match(other, right, re.I) for other, _ in _DEGREES)
                   for pattern, _ in _DEGREES):
                continue
            if any(left.casefold().endswith(alias) for alias in _CITY_ALIASES) and any(
                right.casefold().startswith(alias) for alias in _CITY_ALIASES
            ):
                continue
        end = match.start()
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if end > start:
            yield start, end
        start = match.end()
    end = len(text)
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if end > start:
        yield start, end


def _rule(dimension: str, evidence: EvidenceSpan, **values) -> ConditionRule:
    return ConditionRule(dimension=dimension, evidence=[evidence], **values)


def _uncertain(dimension: str, evidence: EvidenceSpan, note: str) -> ConditionRule:
    # An unsupported preference still is a preference, never a hard blocker.
    return _rule(dimension, evidence, kind="preferred" if _PREFERRED.search(evidence.text) else "uncertain", operator="unknown", note=note)


def _unrestricted(dimension: str, evidence: EvidenceSpan) -> ConditionRule:
    if re.search(r"不接受|不招|不面向|不含|不包含|不适用|不属于|不得|不能|谢绝|勿投|排除|除外|不包括|\b(?:except|excluding)\b", evidence.text, re.I):
        return _uncertain(dimension, evidence, "不限表述同时包含排除条件，不能直接视为无门槛。")
    return _rule(dimension, evidence,
                 kind="preferred" if _PREFERRED.search(evidence.text) else "unrestricted",
                 operator="any")


def _kind(text: str) -> str:
    return "preferred" if _PREFERRED.search(text) else "required"


def _graduation(text: str, evidence: EvidenceSpan) -> ConditionRule:
    if re.search(r"(?:毕业(?:年份|时间|届次)|届次)\s*[:：]?\s*不限|不限\s*(?:毕业)?届次|any\s+graduation\s+year", text, re.I):
        return _unrestricted("graduation_year", evidence)
    if (_NEGATIVE.search(text) or
        re.search(r"20\d{2}\s*(?:[-/.年]\s*\d{1,2}(?!\d)|年?\s*\d{1,2}\s*月)|\b(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\b", text, re.I)):
        return _uncertain("graduation_year", evidence, "毕业时间含否定、细粒度日期或未支持的边界，需要核对原文。")
    inclusive_lower = re.search(r"(?P<year>20\d{2})\s*届\s*及(?:以后|之后)", text)
    if inclusive_lower is not None:
        if len(re.findall(r"20\d{2}", text)) != 1:
            return _uncertain("graduation_year", evidence, "开放届次边界与多个年份混合，需确认其适用范围。")
        return _rule("graduation_year", evidence, kind=_kind(text), operator="min",
                     years=[int(inclusive_lower.group("year"))])
    if re.search(r"以前|以后|之前|之后|不晚于|不早于|截至|截止|最晚|最早|(?:20\d{2}(?:年|届)?|届次)\s*及?(?:以上|以下)|\bbefore\b|\bafter\b", text, re.I):
        return _uncertain("graduation_year", evidence, "毕业时间含否定、细粒度日期或未支持的边界，需要核对原文。")
    # Require a graduation anchor adjacent to the year expression; a project
    # year elsewhere in a sentence is not a graduation requirement.
    expression = r"20\d{2}(?:\s*(?:年|届)?\s*(?:[、,，/或和与&]|[-–—~～至到])\s*20\d{2})*"
    match = re.search(rf"(?P<years>{expression})\s*年?\s*(?:届|毕业|graduates?\b|graduation\b)", text, re.I)
    if match is None:
        match = re.search(rf"(?:毕业(?:年份|届次|时间)?\s*[:：]?|\bclass\s+of\s+|\bgraduat(?:ing|ion|e[sd]?)\s+(?:in\s+)?)(?P<years>{expression})", text, re.I)
    if match is None:
        return _uncertain("graduation_year", evidence, "未识别明确的毕业届次，不能从项目年份推断。")
    value = match.group("years")
    years = list(dict.fromkeys(int(year) for year in re.findall(r"20\d{2}", value)))
    if re.search(r"[-–—~～至到]", value):
        if len(years) != 2 or years[0] > years[1] or years[1] - years[0] > 20:
            return _uncertain("graduation_year", evidence, "毕业届次区间不明确。")
        years = list(range(years[0], years[1] + 1))
    return _rule("graduation_year", evidence, kind=_kind(text), operator="in", years=years)


def _degree_mentions(text: str) -> list[tuple[int, int, str]]:
    """Expand lexical degree ranges without treating postgraduate as master only."""
    found = [(match.start(), match.end(), degree) for pattern, degree in _DEGREES
             for match in re.finditer(pattern, text, re.I)]
    for match in re.finditer(r"(?<!硕士)(?<!博士)研究生|硕博(?!连读)", text):
        found.extend((match.start(), match.end(), degree) for degree in ("master", "doctor"))
    return found


def _degree_capability(text: str) -> bool:
    """Recognize a degree-labelled ability branch, never a state/level gate."""
    scope = re.sub(r"^\s*(?:[-•]\s*|\d{1,2}[、.)）]\s*)", "", text)
    match = re.match(
        r"(?:对于|针对)?(?:本科生?|硕士(?:研究生|生)?|博士(?:研究生|生)?|研究生)"
        r"\s*(?:要求\s*[:：]|重点考察|希望具备|应具备|需具备|须具备|具备|需有|须有|应有|有|能够|能独立|应能够)", scope,
    )
    if match is None:
        return False
    # A genuine status, degree threshold, exclusion or waiver must stay visible
    # to the applicant evaluator, even when it shares a sentence with abilities.
    tail = scope[match.end():]
    return not re.search(
        r"在读|在校|毕业|取得|获得.{0,4}(?:学历|学位)|持有.{0,4}(?:学历|学位)|学历|学位|本科|硕士|博士|研究生|学士|大专|专科"
        r"|或者|(?:^|[，,；;])\s*或|不接受|不招|仅限|仅接受|不得|不能"
        r"|或\s*(?:20\d{2}|[一二三四五六七八九十\d]+\s*年|社会人士|同等|等同)"
        r"|\b(?:enrolled|pursuing|completed|obtained|degree|or|unless|waiv\w*)\b", tail, re.I,
    )


def _student_applicant_scope(text: str) -> bool:
    """Infer enrollment only from a student applicant list, not background prose."""
    scope = re.sub(r"^\s*(?:[-•]\s*|\d{1,2}[、.)）]\s*)", "", text)
    if scope == "研究生":
        return False
    student = r"(?:高中生|中专生|职高生|大专生|专科生|本科生|硕士研究生|博士研究生|硕士生|博士生|研究生)"
    prefix = (
        r"(?:(?:招募对象|招聘对象|招聘范围|申请对象|应聘对象|任职要求|申请资格|学历(?:要求)?)\s*[:：]?\s*)?"
        r"(?:(?:本岗位|本职位|应聘者|申请者)\s*)?"
        r"(?:(?:仅限|只限|仅面向|只面向|面向|仅招收|仅招募|招收|招募|要求(?:为)?|须为|必须为)\s*)?"
        r"(?:[A-Za-z\u4e00-\u9fff、/&+\-\s]+专业(?:的)?)?"
    )
    return re.fullmatch(prefix + student + r"(?:\s*(?:[、，,/／和与或]|或者)\s*" + student + r")*\s*", scope) is not None


def _degree_joins(source: str) -> tuple[dict[int, int], set[int]]:
    """Join clear comma degree lists only for the degree dimension.

    The shared clause iterator and all four other condition dimensions retain
    their original spans. Mixed-dimension expressions are deliberately excluded.
    """
    clauses = list(_clauses(source))
    merged, suppressed = {}, set()
    word = r"(?:研究生|博士(?:研究生|生)?|硕士(?:研究生|生)?|硕博|本科生?|学士|大专|专科)"
    for index, (start, end) in enumerate(clauses):
        if start in suppressed:
            continue
        cursor = index + 1
        while cursor < len(clauses):
            following, stop = clauses[cursor]
            left, right = source[start:end], source[following:stop]
            if (source[end:following].strip() not in {",", "，"}
                    or not re.search(word + r"\s*$", left)
                    or not re.match(word, right)
                    or _PREFERRED.search(left + right)
                    or _degree_capability(left) or _degree_capability(right)
                    or _non_applicant_degree_mention(left) or _non_applicant_degree_mention(right)
                    or re.match(r"\s*[（(]\s*(?:优先|加分|更佳|preferred|a\s+plus|非必须|非必需|optional|not\s+required)", source[stop:], re.I)
                    or _mentioned_dimensions(left + right) != {"degree"}):
                break
            end = stop
            suppressed.add(following)
            merged[start] = end
            cursor += 1
    return merged, suppressed


def _degree(text: str, evidence: EvidenceSpan) -> ConditionRule:
    if _degree_capability(text):
        return _rule("degree", evidence, kind=_kind(text), operator="unknown",
                     degrees=sorted({degree for _, _, degree in _degree_mentions(text)}, key=_RANK.get),
                     degree_scope="conditional_capability",
                     note="按学历分组的能力说明，不作为所有申请人的共同学历门槛；项目或研究能力仍需核对。")
    if re.search(r"(?:学历|学位)\s*[:：]?\s*不限|不限(?:学历|学位)|no\s+degree\s+(?:requirement|required)|any\s+degree", text, re.I):
        return _unrestricted("degree", evidence)
    if re.search(r"博士后|\bpostdoc", text, re.I):
        return _uncertain("degree", evidence, "博士后属于经历而非新的学历层级，需核对招聘要求。")
    if re.search(r"非(?:必须|必需|硬性|强制)|不作(?:硬性)?要求|不做(?:硬性)?要求|\boptional\b|\bnot\s+required\b", text, re.I):
        return _uncertain("degree", evidence, "学历或状态并非明确硬性要求，需要核对适用范围。")
    mentions = _degree_mentions(text)
    degrees = sorted({degree for _, _, degree in mentions}, key=_RANK.get)
    if re.search(r"硕博连读", text):
        return _uncertain("degree", evidence, "连读项目的身份不能只按最高学历比较。")
    if re.search(r"(?<!硕士)(?<!博士)研究生\s*(?:导师|专业说明|项目说明|团队说明)", text):
        return _uncertain("degree", evidence, "研究生的提及不构成明确申请人学历范围。")
    if (re.search(r"(?<!硕士)(?<!博士)研究生", text) and not re.search(
            r"学历|学位|在读|在校|要求|资格|应届|本科|硕士|博士|背景|优先|加分", text)
            and not re.fullmatch(r"\s*(?:[-•]\s*|\d+[、.)]\s*)?(?:[\w、/\s]+专业)?研究生\s*", text)):
        return _uncertain("degree", evidence, "研究生仅作为背景或其他说明出现，学历范围需确认。")
    if _NEGATIVE.search(text):
        return _uncertain("degree", evidence, "学历层级或否定条件尚不能可靠比较。")
    # A supported degree list is distinct from an alternative applicant identity
    # or waiver. A professional-subject OR before the degree is not a degree OR.
    for alternative in re.finditer(r"或者|或|[/／]|\bor\b", text, re.I):
        left, right = text[:alternative.start()], text[alternative.end():]
        if re.match(r"\s*(?:above|higher|below)\b", right, re.I):
            continue
        if not _degree_mentions(left) and re.search(r"(?:专业|领域|方向)\s*(?:的)?\s*(?:在读|在校)?\s*$", left + right[:min((a for a, _, _ in _degree_mentions(right)), default=0)]):
            continue
        if bool(_degree_mentions(left)) != bool(_degree_mentions(right)):
            return _uncertain("degree", evidence, "学历与未明确的其他身份存在任选关系。")
    if not degrees:
        # A general student requirement is a state constraint, not an unknown
        # degree level. Only explicit applicant-facing forms qualify; merely
        # serving, interviewing or collaborating with students is not a gate.
        scope_text = re.sub(r"^\s*(?:[-•]\s*|\d{1,2}[、.)）]\s*)", "", text)
        postgraduate = re.search(r"在读研究生|研究生在读", scope_text)
        if postgraduate is not None:
            before, after = scope_text[:postgraduate.start()], scope_text[postgraduate.end():]
            if (re.search(r"或者|或|\bor\b", after, re.I)
                    or (re.search(r"或者|或|\bor\b", before, re.I) and not before.rstrip().endswith("专业"))):
                return _uncertain("degree", evidence, "研究生在读与其他候选身份存在未支持的任选关系。")
            return _rule("degree", evidence, kind=_kind(text), operator="in",
                         degrees=["master", "doctor"], degree_status="enrolled")
        professional_student = re.fullmatch(
            r"[A-Za-z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff、/\s&+\-]*专业(?:的)?(?:在校生|在校学生|在读学生|在读)", scope_text,
        )
        explicit_student = (
            re.search(r"(?:^|[:：])\s*(?:面向|仅面向|只面向|仅限|限|要求|须为|必须为|应为)?\s*(?:全体|全日制|目前|当前)?(?:在校生|在校学生|在读学生)\s*$", scope_text)
            or re.search(r"(?:本岗位|本职位|应聘者|申请者|日常实习|暑期实习|寒假实习)\s*(?:面向|仅面向|仅限|限|要求(?:为)?|须为|必须为|应为)\s*(?:全体|目前|当前)?(?:在校生|在校学生|在读学生)\s*$", scope_text)
            or re.fullmatch(r"(?:must\s+be\s+)?(?:currently\s+)?enrolled(?:\s+(?:as\s+)?(?:a\s+)?student)?", scope_text, re.I)
            or re.fullmatch(r"20\d{2}\s*届\s*(?:在校生|在校学生|在读学生)", scope_text)
            or professional_student
        )
        if explicit_student:
            return _rule("degree", evidence, kind=_kind(text), operator="any", degree_status="enrolled")
        return _uncertain("degree", evidence, "学历层级或否定条件尚不能可靠比较。")
    enrolled = bool(re.search(r"在读|在校|\benrolled\b|\bcurrently\s+(?:pursuing|studying)\b|\bpursuing\b", text, re.I)) or _student_applicant_scope(text)
    completed = bool(re.search(r"已取得|已获得|已毕业|持有|\b(?:completed|obtained|earned|hold(?:ing)?)\b", text, re.I))
    if enrolled and completed:
        return _uncertain("degree", evidence, "同一学历表述混合在读与已取得，需要确认对应层级。")
    if enrolled and len(degrees) > 1 and not _student_applicant_scope(text):
        states = list(re.finditer(r"在读|在校|\benrolled\b|\bcurrently\s+(?:pursuing|studying)\b|\bpursuing\b", text, re.I))
        first, last = min(a for a, _, _ in mentions), max(b for _, b, _ in mentions)
        common_state = any(state.end() <= first or state.start() >= last for state in states)
        branches = [part for part in re.split(r"或者|或|[/／、,，]|\bor\b", text, flags=re.I) if _degree_mentions(part)]
        if not common_state and not all(re.search(r"在读|在校|\benrolled\b|\bpursuing\b", part, re.I) for part in branches):
            return _uncertain("degree", evidence, "在读状态只明确属于部分学历分支，需要确认其余身份。")
    minimum = bool(re.search(r"及?以上|不低于|至少|\bor\s+(?:above|higher)\b|\bat\s+least\b|\bminimum\b", text, re.I))
    maximum = bool(re.search(r"及?以下|不高于|最高|\bor\s+below\b|\bat\s+most\b", text, re.I))
    if len(degrees) > 1 and (minimum or maximum) and re.search(r"或者|或|[/／]|\bor\b", text, re.I):
        return _uncertain("degree", evidence, "学历分支与上下界混合，需确认各分支范围和状态。")
    if minimum and maximum:
        return _uncertain("degree", evidence, "学历上下界作用域不明确。")
    return _rule("degree", evidence, kind=_kind(text), operator="min" if minimum else "max" if maximum else "in",
                 degrees=[degrees[0]] if minimum else [degrees[-1]] if maximum else degrees,
                 degree_exclusive=bool(re.search(r"仅限|只限|仅接受|只接受|仅招(?:收|募)?|只招(?:收|募)?|仅面向|只面向|限定为|必须为|\bonly\b|\bexclusively\b", text, re.I)),
                 degree_status="enrolled" if enrolled else "completed" if completed else None)


def _non_applicant_degree_mention(text: str) -> bool:
    """A student's advisor or the people served do not define the applicant."""
    scope = re.sub(r"^\s*(?:[-•]\s*|\d{1,2}[、.)）]\s*)", "", text)
    if re.search(r"研究生导师.{0,12}(?:知情|同意|批准|许可)", scope):
        return True
    if re.match(r"(?:团队|部门|同事).{0,8}(?:招收|招聘|指导|培养)", scope):
        return True
    if re.match(r"(?:与|和|同|负责|参与|支持|协助|帮助|服务|指导|培训|辅导|培养|教育)", scope):
        return True
    return bool(re.match(r"(?:有|具备).{0,8}(?:指导|辅导|培训|培养).{0,12}(?:研究生|在校生|在读学生)", scope))


def _number(value: str) -> float:
    if value == "半":
        return 0.5
    digits = {character: number for number, character in enumerate("零一二三四五六七八九")}
    digits["两"] = 2
    if "十" in value:
        left, right = value.split("十")
        return (digits.get(left, 1) * 10) + digits.get(right, 0)
    if value in digits:
        return float(digits[value])
    return float(value)


def _months(number: str, unit: str) -> float:
    return _number(number) * (12 if unit.casefold().startswith("year") or unit == "年" else 1)


def _duration(text: str, evidence: EvidenceSpan, dimension: str) -> ConditionRule:
    if dimension == "experience" and re.search(r"(?:工作)?经验\s*[:：]?\s*不限|不限(?:工作)?经验|无(?:工作)?经验要求|无需(?:工作)?经验|no\s+(?:work\s+)?experience\s+(?:required|necessary)|experience\s+(?:is\s+)?not\s+required", text, re.I):
        return _unrestricted(dimension, evidence)
    if dimension == "internship_duration" and re.search(r"(?:实习)?(?:时长|期限|时间)\s*[:：]?\s*不限|实习时长无要求|no\s+(?:minimum\s+)?internship\s+duration", text, re.I):
        return _unrestricted(dimension, evidence)
    if _NEGATIVE.search(text):
        return _uncertain(dimension, evidence, "表述包含未支持的否定条件。")
    if dimension == "experience":
        # General work-experience months cannot establish domain/project tenure.
        if re.search(r"相关|行业|领域|项目|开发|管理|研发|实习|\b(?:relevant|industry|project|internship|development|management)\b", text, re.I):
            return _uncertain(dimension, evidence, "要求特定领域、项目或实习经验，不能仅用总工作月数判断。")
        scrubbed = re.sub(r"\b(?:work|working|professional|experience|years?|months?|at|least|most|minimum|maximum|of|over|under|required|preferred|to|more|than|up)\b", "", text, flags=re.I)
        if re.search(r"[A-Za-z]{2,}", scrubbed):
            return _uncertain(dimension, evidence, "经验包含具体技能或未支持的限定，需核对。")
    if re.search(r"每周|每天|每月|\bper\s+(?:week|day)\b", text, re.I):
        return _uncertain(dimension, evidence, "到岗频率不能换算为可实习或工作时长。")
    range_match = _RANGE.search(text)
    if range_match:
        try:
            low = _months(range_match.group("first"), range_match.group("unit1") or range_match.group("unit2"))
            high = _months(range_match.group("second"), range_match.group("unit2"))
        except ValueError:
            return _uncertain(dimension, evidence, "时长数字写法尚不支持。")
        if low > high or high > 1200:
            return _uncertain(dimension, evidence, "时长区间不合理或倒置。")
        return _rule(dimension, evidence, kind=_kind(text), operator="range", min_months=low, max_months=high)
    values = list(_DURATION.finditer(text))
    if len(values) != 1:
        return _uncertain(dimension, evidence, "缺少可直接比较的单一时长或明确区间。")
    match = values[0]
    try:
        months = _months(match.group("number"), match.group("unit"))
    except ValueError:
        return _uncertain(dimension, evidence, "时长数字写法尚不支持。")
    if re.search(r"年半|月半", text):
        return _uncertain(dimension, evidence, "复合时长写法需要核对。")
    if months > 1200:
        return _uncertain(dimension, evidence, "时长超出支持范围。")
    minimum = bool(re.search(r"至少|不少于|不低于|及?以上|起|\bat\s+least\b|\bminimum\b|\bor\s+more\b|\d\s*\+", text, re.I))
    maximum = bool(re.search(r"最多|不超过|不多于|以内|及?以下|至多|\bat\s+most\b|\bmaximum\b|\bup\s+to\b|\bor\s+less\b", text, re.I))
    if minimum and maximum or re.search(r"超过|少于|大于|小于|\b(?:over|under|more\s+than|less\s+than)\b", re.sub(r"不超过|不少于|不大于|不小于", "", text), re.I):
        return _uncertain(dimension, evidence, "严格或混合作用域边界需要核对，不能当作包含边界。")
    # A bare duration is not silently treated as an inclusive minimum.
    if not minimum and not maximum:
        return _uncertain(dimension, evidence, "给出了时长，但未明确最低、最高或区间要求。")
    return _rule(dimension, evidence, kind=_kind(text), operator="max" if maximum else "min",
                 min_months=None if maximum else months, max_months=months if maximum else None)


def _city(text: str, evidence: EvidenceSpan, *, structured: bool) -> ConditionRule:
    if re.search(r"(?:城市|地点)\s*[:：]?\s*不限|不限(?:城市|地点)|any\s+(?:city|location)", text, re.I):
        return _unrestricted("city", evidence)
    candidate = text
    if not structured:
        label = _CITY_LABEL.search(text)
        if label is None:
            return _uncertain("city", evidence, "工作城市表述尚不能可靠识别。")
        candidate = text[label.end():].lstrip(" ：:")
    parts = re.split(r"[、,，/|;；]|\s+(?:or|and)\s+|或", candidate, flags=re.I)
    cities = [normalize_city(part.strip(" 。.")) for part in parts]
    if not cities or any(city is None for city in cities) or _NEGATIVE.search(text):
        return _uncertain("city", evidence, "存在未知城市、远程或其他位置限定，请核对来源。")
    return _rule("city", evidence, kind=_kind(text), operator="in", cities=list(dict.fromkeys(cities)))


def _mentioned_dimensions(text: str) -> set[str]:
    result = set()
    if _GRADUATION.search(text):
        result.add("graduation_year")
    if _DEGREE_CONTEXT.search(text):
        result.add("degree")
    if _EXPERIENCE.search(text):
        result.add("experience")
    if _INTERNSHIP.search(text) and not _EXPERIENCE.search(text):
        result.add("internship_duration")
    if _CITY_LABEL.search(text):
        result.add("city")
    return result


def _has_correlated_alternatives(text: str) -> bool:
    """Detect obvious cross-dimension OR without implementing a Boolean tree.

    Pure degree/year lists remain supported. Independent dimension filters may
    not represent paired alternatives such as cohort A/degree A OR B/B.
    """

    for match in re.finditer(r"或者|或|\bor\b", text, re.I):
        right = text[match.end():]
        if re.match(r"\s+(?:above|higher|below|more|less)\b", right, re.I):
            continue
        left_dimensions = _mentioned_dimensions(text[:match.start()])
        right_dimensions = _mentioned_dimensions(right)
        if left_dimensions and right_dimensions and len(left_dimensions | right_dimensions) > 1:
            return True
    return False


def extract_conditions(job: JobRead) -> list[ConditionRule]:
    """Return exact source spans; never invent a rule for absent information."""

    rules: list[ConditionRule] = []
    if job.city and job.city.strip():
        rules.append(_city(job.city, _span("city", job.city, 0, len(job.city)), structured=True))
    for field in ("title", "description"):
        source = getattr(job, field) or ""
        degree_joins, degree_suppressed = _degree_joins(source)
        previous: tuple[int, int] | None = None
        previous_rule_start = len(rules)
        preference_heading: EvidenceSpan | None = None
        for start, end in _clauses(source):
            text = source[start:end]
            evidence = _span(field, source, start, end)
            if re.fullmatch(r"(?:加分项|优先(?:条件|项)|优选条件|preferred\s+qualifications|nice\s+to\s+have)\s*[:：]?", text, re.I):
                preference_heading = evidence
                previous = (start, end)
                previous_rule_start = len(rules)
                continue
            if re.fullmatch(r"(?:任职要求|基本要求|必须条件|硬性要求|岗位职责|required\s+qualifications|requirements)\s*[:：]?", text, re.I):
                preference_heading = None
                previous = (start, end)
                previous_rule_start = len(rules)
                continue
            if (previous is not None and
                source[previous[1]:start].strip() in {"（", "("} and
                re.fullmatch(r"优先|加分|更佳|preferred|a\s+plus", text, re.I) and
                source[end:].lstrip().startswith(("）", ")"))):
                for rule in rules[previous_rule_start:]:
                    rule.kind = "preferred"
                    rule.evidence.append(evidence)
                previous = (start, end)
                previous_rule_start = len(rules)
                continue
            if (previous is not None and source[previous[1]:start].strip() in {"（", "(", "，", ","}
                    and re.fullmatch(r"非(?:必须|必需|硬性要求)|不作硬性要求|optional|not\s+required", text, re.I)):
                for rule in rules[previous_rule_start:]:
                    rule.kind = "preferred"
                    rule.evidence.append(evidence)
                previous = (start, end)
                previous_rule_start = len(rules)
                continue
            if re.fullmatch(r"(?:学历(?:要求)?|工作经验|经验要求|实习时长|工作地点|毕业届次)\s*[:：]?", text):
                continue
            if previous is not None and re.search(r"\n\s*\n", source[previous[1]:start]):
                preference_heading = None
            rule_start = len(rules)
            if previous is not None and re.match(r"^(?:[-•]\s*|\d+[、.)]\s*)?(?:或者|或|or\b)", text, re.I):
                # An OR continued after punctuation must not turn its left
                # branch into an independent hard filter. Preserve both spans.
                previous_text = source[previous[0]:previous[1]]
                dimensions = _mentioned_dimensions(previous_text) | _mentioned_dimensions(text)
                if dimensions and rules[previous_rule_start:rule_start]:
                    for prior_rule in rules[previous_rule_start:rule_start]:
                        prior_rule.kind = "preferred" if preference_heading is not None else "uncertain"
                        prior_rule.note = "条件包含跨分句的任选关系，不能将其中一个分支作为独立门槛。"
                        prior_rule.evidence.append(evidence)
                    for dimension in sorted(dimensions):
                        continuation = _uncertain(dimension, evidence, "条件包含跨分句的任选关系，需要核对原文。")
                        if preference_heading is not None:
                            continuation.kind = "preferred"
                            continuation.evidence.insert(0, preference_heading)
                        rules.append(continuation)
                    previous = (start, end)
                    previous_rule_start = rule_start
                    continue
            if _has_correlated_alternatives(text):
                for dimension in sorted(_mentioned_dimensions(text)):
                    rules.append(_degree(text, evidence) if dimension == "degree" and _degree_capability(text) else
                                 _uncertain(dimension, evidence, "条件包含跨维度的关联任选关系，首版不能拆开判定，请核对原文。"))
                if preference_heading is not None:
                    for rule in rules[rule_start:]:
                        rule.kind = "preferred"
                        rule.evidence.insert(0, preference_heading)
                previous = (start, end)
                previous_rule_start = rule_start
                continue
            if _GRADUATION.search(text):
                rules.append(_graduation(text, evidence))
            if start not in degree_suppressed:
                degree_text = source[start:degree_joins.get(start, end)]
                if _DEGREE_CONTEXT.search(degree_text) and not _non_applicant_degree_mention(degree_text):
                    rules.append(_degree(degree_text, _span(field, source, start, degree_joins.get(start, end))))
            if _EXPERIENCE.search(text):
                rules.append(_duration(text, evidence, "experience"))
            if _INTERNSHIP.search(text) and not _EXPERIENCE.search(text) and (
                _DURATION.search(text) or re.search(r"时长|期限|至少|最多|每周|不限|duration|months?|years?", text, re.I)
            ):
                rules.append(_duration(text, evidence, "internship_duration"))
            elif previous is not None and _DURATION.search(text):
                previous_start, previous_end = previous
                prefix = source[previous_start:previous_end]
                separator = source[previous_end:start].strip()
                if separator in {"（", "("} and _INTERNSHIP.search(prefix) and not _EXPERIENCE.search(prefix):
                    rule = _duration(text, evidence, "internship_duration")
                    rule.evidence.insert(0, _span(field, source, previous_start, previous_end))
                    rules.append(rule)
            if _CITY_LABEL.search(text) or re.search(r"远程(?:办公|工作|实习)|(?:支持|可)(?:全)?远程|\bremote\b", text, re.I):
                rules.append(_city(text, evidence, structured=False))
            if preference_heading is not None:
                for rule in rules[rule_start:]:
                    rule.kind = "preferred"
                    rule.evidence.insert(0, preference_heading)
            previous = (start, end)
            previous_rule_start = rule_start
    return rules
