"""Finite rules for role fit, quoted skill importance, and recommendation order."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
import re

from app.eligibility.contracts import EvidenceSpan
from app.recommendations.quality_contracts import (
    DetectedDirection, DirectionFit, RankingSupport, SkillRequirement, TargetDirection, TargetDirectionCheck,
)
from app.schemas.job_response import JobRead
from app.services.skill_vocabulary import SKILL_ALIASES, normalize_skill


_ROLE_SUFFIX = r"(?:开发|研发|工程师|实习生|实习岗|技术员|岗位|[／/与和、&])"
_TITLE_PATTERNS: dict[DetectedDirection, re.Pattern] = {
    "ai_application": re.compile(r"(?:AI|人工智能|大模型|LLM)\s*应用\s*(?:开发|研发|工程师)|(?:智能体|(?:AI\s*)?Agent|LLM|RAG|大模型)\s*(?:应用)?\s*(?:开发|研发|工程师)|\b(?:AI application|LLM|AI agent)\s+(?:developer|engineer)", re.I),
    "backend": re.compile(r"(?:后端|后台|服务端)\s*" + _ROLE_SUFFIX + r"|(?<![a-z])back[ -]?end\s+(?:software\s+)?(?:developer|engineer|intern)", re.I),
    "computer_vision": re.compile(r"(?:计算机视觉|机器视觉|视觉算法|图像算法|CV\s*算法|CV(?=\s*工程师))\s*(?:方向|算法)?\s*(?:开发|研发|工程师|实习生|[／/与和、&])|\bcomputer vision\s+(?:research|engineer|developer|intern)", re.I),
    "data": re.compile(r"(?:大数据|数据)\s*(?:开发|工程师|分析(?:师|工程师|实习生|岗|[／/与和、&]|$)|研发)|\bdata\s+(?:engineer|analyst|analytics\s+engineer)", re.I),
    "frontend": re.compile(r"前端\s*" + _ROLE_SUFFIX + r"|(?<![a-z])front[ -]?end\s+(?:software\s+)?(?:developer|engineer|intern)", re.I),
    "test_development": re.compile(r"测试开发|测试研发|自动化测试(?:工程师|实习生|开发|岗)|(?:软件|接口)测试(?:工程师|实习生|岗)|\b(?:test automation|software test|QA automation)\s+(?:engineer|developer|intern)|\bSDET\b", re.I),
    "devops": re.compile(r"运维\s*(?:开发|研发|工程师|实习生|岗)|(?<![a-z])(?:DevOps|SRE)(?=\s*(?:工程师|实习生|岗|engineer|developer|intern|[／/与和、&]|$))", re.I),
    "security": re.compile(r"(?:信息|网络|应用|数据)?安全\s*(?:开发|研发|工程师)|\b(?:security engineer|security developer)", re.I),
}
_OTHER_ROLE = re.compile(
    r"(?:公关|公共关系|营销|品牌传播|市场推广|市场营销|市场运营|销售|人力资源)\s*(?:策划|运营)?\s*(?:经理|实习生|岗|专员|主管|顾问|代表|助理|总监|$)"
    r"|(?:产品|项目)\s*(?:经理|管理(?:实习生|岗|专员|工程师))|产品\s*(?:实习生|专员|助理|总监|负责人)|生物医学工程师"
    r"|(?:品牌视觉|视觉设计|平面设计|交互设计)\s*(?:设计师|实习生|岗|[-—－]|$)"
    r"|\b(?:product manager|project manager|marketing (?:specialist|intern|manager)|public relations (?:specialist|intern|manager))\b", re.I,
)
# A generic title can be clarified by an explicit responsibility. Mentions of
# tools, degree subjects, job requirements, and collaboration partners do not suffice.
_DUTY_ACTION = r"(?:负责|承担|参与)"
_DUTY_SUBJECT = re.compile(r"(?:(?:本岗位|本职位|本岗|该岗位|该职位|你|您|实习生)\s*)?(?:(?:将|主要|独立)\s*)*")
_DUTY_PATTERNS: dict[DetectedDirection, re.Pattern] = {
    "ai_application": re.compile(_DUTY_ACTION + r"(?:开发|搭建|构建)?\s*(?:AI|人工智能|大模型|LLM|智能体|Agent|RAG)\s*(?:应用|系统|平台)(?:的)?(?:开发|研发|建设)|" + _DUTY_ACTION + r"(?:开发|构建|搭建)\s*(?:AI|大模型|LLM|智能体|Agent|RAG)\s*(?:应用|系统|平台)", re.I),
    "backend": re.compile(_DUTY_ACTION + r"(?:开发|维护|设计)?\s*(?:后端|后台|服务端)(?:服务|接口|系统|平台)?(?:的)?(?:设计|开发|研发|维护)|" + _DUTY_ACTION + r"(?:开发|维护)\s*(?:后端|服务端)(?:服务|接口|系统)"),
    "frontend": re.compile(_DUTY_ACTION + r"(?:Web\s*)?前端(?:页面|应用|系统)?(?:的)?(?:开发|研发)|" + _DUTY_ACTION + r"开发(?:Web\s*)?前端(?:页面|应用|系统)", re.I),
    "computer_vision": re.compile(_DUTY_ACTION + r"(?:研发|开发)?(?:计算机视觉|机器视觉|图像识别|图像分割|目标检测|视觉算法)(?:算法|系统)?(?:的)?(?:研发|开发|优化)|" + _DUTY_ACTION + r"(?:研发|开发)(?:计算机视觉|图像识别|图像分割|目标检测)(?:算法|系统)"),
    "data": re.compile(_DUTY_ACTION + r"(?:建设|开发|搭建)?(?:数据仓库|数仓|数据管道|ETL任务)(?:的)?(?:开发|建设|维护)|" + _DUTY_ACTION + r"(?:开发|搭建)(?:数据仓库|数仓|数据管道)", re.I),
    "test_development": re.compile(_DUTY_ACTION + r"(?:测试框架|自动化测试平台|自动化测试框架)(?:的)?(?:开发|建设)|" + _DUTY_ACTION + r"(?:开发|搭建)(?:自动化测试框架|自动化测试平台)"),
    "devops": re.compile(_DUTY_ACTION + r"(?:构建|维护|搭建)\s*(?:CI/CD|持续集成)(?:流水线|平台)", re.I),
    "security": re.compile(_DUTY_ACTION + r"(?:安全平台|安全检测引擎)(?:的)?(?:开发|研发)|" + _DUTY_ACTION + r"(?:开发|研发)(?:安全平台|安全检测引擎)"),
}

# A role may deliver several technical functions. These patterns describe the
# applicant's assigned work, rather than treating every technical noun as a role.
_DELIVERY_ACTION = r"(?:(?:负责|承担|参与)(?:开发|研发|设计|构建|搭建|建设)?|设计(?:和|与|并)?开发|设计和实现|开发|研发|构建|搭建|建设)"
_TASK_PREFIX = r"[^，,。；;\r\n]{0,32}?"
_AI_OBJECT = (
    r"(?:(?:AI\s*|智能)?Agent(?![A-Za-z0-9_])|智能体|(?:AI|人工智能|大模型|LLM)\s*应用|RAG(?![A-Za-z0-9_])(?:\s*(?:应用|系统|平台))?)"
    # A domain modifier is not the object being built: an observability platform
    # serving an Agent scenario does not thereby become an Agent application.
    r"(?!\s*(?:应用\s*)?(?:场景|领域|生态|团队|部门|公司|业务线))"
    r"(?!\s*(?:应用\s*)?的?\s*(?:可观测|监控|存储|日志|指标|告警)(?:平台|系统|服务|链路|工具))"
)
_DELIVERY = r"(?:设计|开发|研发|建设|构建|搭建|集成|接入|部署|优化|评测)"
_COMPOUND_DUTY_PATTERNS = {
    "ai_application": re.compile(
        _DELIVERY_ACTION + _TASK_PREFIX + _AI_OBJECT + r"[^。；;\r\n]{0,36}?" + _DELIVERY
        + r"|(?:负责|承担|参与)?(?:设计和开发|设计和实现|开发|研发|构建|搭建|建设)\s*" + _TASK_PREFIX + _AI_OBJECT, re.I,
    ),
    "backend": re.compile(
        _DELIVERY_ACTION + _TASK_PREFIX + r"(?:后端|后台|服务端)(?:业务|服务|接口|系统|平台)?[^。；;\r\n]{0,24}?(?:设计|开发|研发|维护|建设)"
        + r"|(?:负责|承担|参与)?(?:开发|研发|建设|维护)\s*(?:后端|后台|服务端)(?:服务|接口|系统|平台)", re.I,
    ),
    "computer_vision": re.compile(
        _DELIVERY_ACTION + _TASK_PREFIX + r"(?:视频|图像|视觉|计算机视觉|机器视觉|CV)"
        r"[^，,。；;\r\n]{0,16}?模型[^。；;\r\n]{0,36}?(?:接入|推理部署|部署|移植|优化|研发|开发)"
        + r"|(?:负责|承担|参与)?(?:接入|部署|移植|开发|研发|优化)\s*(?:视频|图像|视觉|CV)[^。；;\r\n]{0,12}?模型", re.I,
    ),
}
_TASK_PRELUDE = re.compile(r"(?:面向|针对|围绕)[^，,。；;\r\n]{1,100}[，,]\s*")
_NON_ASSIGNED = re.compile(
    r"(?:与|和|配合|协同)(?:负责|承担|参与)|(?:曾经?|有过|要求|经验|优先|团队负责|部门负责|团队讨论)"
    r"|^(?:负责|承担|参与)(?:沟通|协调|调研|跟踪|对接|评审|介绍|推广|宣传|销售|整理|编写)",
)
_ROLE_MENTION_SUFFIX = re.compile(
    r"\s*(?:项目|工作|模块)?(?:的)?(?:同事|同学|团队|部门|工程师|(?:产品)?需求|培训|宣讲|课程|分享|教程|文档|材料|报告|使用指南|销售|推广|宣传|营销|社区|者(?:大会|社区|培训)|成果(?:展示|介绍))",
)
_GENERATION_CONTEXT = re.compile(r"视频生成|图像生成|生成式(?:内容|人工智能|产品|应用)|文生图|文生视频|图生视频")
_PRODUCT_CONTEXT = re.compile(r"APP|应用|产品|业务|场景", re.I)
_MODEL_INTEGRATION = re.compile(r"模型[^。；;\r\n]{0,24}(?:接入|集成|服务建设)")
_VISUAL_AGENT_SCOPE = re.compile(
    r"(?:面向|围绕|针对|覆盖)[^。；;\r\n]{0,24}(?:图像生成|图文理解|视觉内容规划|图文一致性|视频生成|视频理解)"
    r"|(?:图像生成|图文理解|视频生成|视频理解)[^，,。；;\r\n]{0,16}(?:Agent|智能体)", re.I,
)
_NEGATIVE_ROLE_OBJECTS: dict[TargetDirection, re.Pattern] = {
    "ai_application": re.compile(r"(?:AI|人工智能|大模型|LLM)\s*应用|(?:AI\s*)?Agent(?![A-Za-z0-9_])(?:应用|开发|研发|系统|工作|岗位|方向)?|智能体(?:应用|开发|研发|工作|岗位|方向)?|RAG(?:应用|开发|研发|工作|岗位|方向)", re.I),
    "backend": re.compile(r"(?:后端|后台|服务端)(?:服务|接口|系统|平台|业务)?(?:的)?(?:开发|研发|工程师|岗位|工作|方向)?"),
    "computer_vision": re.compile(r"计算机视觉|机器视觉|视觉(?:算法|感知|模型|开发|研发)|图像(?:识别|生成|理解|算法)|图文理解|视频(?:生成|理解|算法)|(?<![A-Za-z0-9_])CV(?:算法|开发|研发|工作|方向)?(?![A-Za-z0-9_])", re.I),
    "data": re.compile(r"(?:大数据|数据)(?:开发|研发|分析|工程师|方向|岗位|工作)"),
    "frontend": re.compile(r"前端(?:页面|服务|系统)?(?:开发|研发|工程师|岗位|工作|方向)?|front[ -]?end", re.I),
    "test_development": re.compile(r"测试开发|测试研发|自动化测试(?:开发|研发|工作|岗位|方向)?|SDET", re.I),
    "devops": re.compile(r"运维(?:开发|研发|岗位|工作|方向)?|DevOps|SRE", re.I),
    "security": re.compile(r"安全(?:开发|研发|工程师|岗位|工作|方向)|信息安全|网络安全"),
}
_ROLE_DENIAL = re.compile(r"(?:不(?:再)?(?:负责|承担|涉及|参与|从事|做)|无需承担|不是|不属于|非)\s*")
_NON_ROLE_DENIAL = re.compile(r"^(?:招聘|培训|审核|评审|沟通|协调|推广|宣传|管理|面试|调研|编写)|经验|背景|专业|优先|同事|同学|培训|招聘|面试|文档|课程|评审")
_NON_ROLE_DENIAL_SUFFIX = re.compile(r"\s*(?:的)?(?:培训|课程|文档|经验|背景|招聘|面试|项目管理|流程管理|团队管理)")
_DIRECTION_NAMES = {
    "ai_application": "AI 应用开发", "backend": "后端开发", "computer_vision": "计算机视觉",
    "data": "数据开发／分析", "frontend": "前端开发", "test_development": "测试开发",
    "devops": "运维／DevOps", "security": "安全研发", "other": "其他职能",
}


def _span(field, source: str, start: int, end: int) -> EvidenceSpan:
    return EvidenceSpan(field=field, text=source[start:end], start=start, end=end)


def evaluate_direction(job: JobRead, targets: Sequence[TargetDirection]) -> DirectionFit:
    if not targets:
        return DirectionFit(status="not_requested", reason="本次未限定岗位方向。")
    directions: list[DetectedDirection] = []
    evidence: list[EvidenceSpan] = []
    positive_evidence: dict[DetectedDirection, list[EvidenceSpan]] = {}
    requested = list(dict.fromkeys(targets))
    title_parts = []
    for part in re.split(r"[（）()，,。；;\n]", job.title):
        # Keep explicit compound roles, but a negated product/technical role is
        # not a positive role clue and cannot trigger protected-role exclusion.
        roles = re.split(r"[/／|｜]|(?:与|和|、)(?=(?:非|不是|不属于))", part)
        positive_roles = [role.strip() for role in roles if role.strip()
                          and not _AMBIGUOUS.search(role)
                          and not _ROLE_DENIAL.match(role.strip())
                          and not re.search(r"(?:经验|背景)(?:者)?优先", role, re.I)]
        if positive_roles:
            title_parts.append("/".join(positive_roles))
    has_other_role = any(_OTHER_ROLE.search(part) for part in title_parts)
    if has_other_role:
        # In "AI产品经理", AI names the product. Only an explicitly separate
        # technical role, e.g. "后端开发／产品经理", can also count.
        title_parts = [role for part in title_parts for role in re.split(r"[/／|｜]", part)
                       if not _OTHER_ROLE.search(role)]
    directions = [direction for direction, pattern in _TITLE_PATTERNS.items()
                  if any(pattern.search(part) for part in title_parts)]
    if has_other_role:
        directions.append("other")
    if directions:
        title_quote = _span("title", job.title, 0, len(job.title))
        evidence.append(title_quote)
        positive_evidence = {direction: [title_quote] for direction in directions}
    # A title's technical role is one source of evidence, not an exclusive
    # classification. Explicit nontechnical titles remain protected unless the
    # title itself also declares a separate technical role.
    if not has_other_role or any(direction != "other" for direction in directions):
        for clause in _direction_task_fragments(job.description):
            if (clause.section in {"core", "bonus", "other"} or _AMBIGUOUS.search(clause.quote.text)
                    or _NON_ASSIGNED.search(clause.quote.text)):
                continue
            # Match the task assigned to the applicant. Verbs describing a
            # colleague ("与负责后端开发的同事协作") do not assign that role.
            task_start = _DUTY_SUBJECT.match(clause.quote.text).end()
            prelude = _TASK_PRELUDE.match(clause.quote.text, task_start)
            if prelude is not None:
                task_start = prelude.end()
            found = []
            for direction, base_pattern in _DUTY_PATTERNS.items():
                patterns = [base_pattern]
                if direction in _COMPOUND_DUTY_PATTERNS:
                    patterns.append(_COMPOUND_DUTY_PATTERNS[direction])
                matches = [pattern.match(clause.quote.text, task_start) for pattern in patterns]
                if any(match and not _ROLE_MENTION_SUFFIX.match(clause.quote.text, match.end()) for match in matches):
                    found.append(direction)
            # Visual model integration is AI application work only when the same
            # assigned task explicitly delivers a generative product or scene.
            text = clause.quote.text
            if ("computer_vision" in found and _GENERATION_CONTEXT.search(text)
                    and _PRODUCT_CONTEXT.search(text) and _MODEL_INTEGRATION.search(text)):
                found.append("ai_application")
            if "ai_application" in found and _VISUAL_AGENT_SCOPE.search(text):
                found.append("computer_vision")
            for direction in found:
                if direction not in directions:
                    directions.append(direction)
                quotes = positive_evidence.setdefault(direction, [])
                if clause.quote not in quotes:
                    quotes.append(clause.quote)
                if clause.quote not in evidence:
                    evidence.append(clause.quote)
    negative_evidence = _direction_denials(job, requested)
    if has_other_role and not any(direction != "other" for direction in directions):
        title_quote = _span("title", job.title, 0, len(job.title))
        for target in requested:
            negative_evidence[target] = [title_quote, *negative_evidence.get(target, [])]
    checks = []
    for target in requested:
        positive = positive_evidence.get(target, [])
        negative = negative_evidence.get(target, [])
        quotes = list(dict.fromkeys((quote.field, quote.start, quote.end, quote.text) for quote in [*positive, *negative]))
        check_evidence = [EvidenceSpan(field=field, start=start, end=end, text=text) for field, start, end, text in quotes]
        label = _DIRECTION_NAMES[target]
        if positive and negative:
            status = "uncertain"
            reason = f"{label}同时存在直接职责和明确否定依据，需核实冲突。"
        elif positive:
            status = "aligned"
            reason = f"原文有本岗直接承担{label}工作的依据。"
        elif negative:
            status = "unrelated"
            reason = f"原文明示不承担{label}工作，或标题明确属于受保护的非技术职能。"
        else:
            status = "uncertain"
            reason = f"当前未能确认{label}的直接职责，也没有明确否定证据，保留待确认。"
        checks.append(TargetDirectionCheck(target=target, status=status, reason=reason, evidence=check_evidence))
        for quote in check_evidence:
            if quote not in evidence:
                evidence.append(quote)
    if not evidence and job.title.strip():
        evidence = [_span("title", job.title, 0, len(job.title))]
    statuses = [check.status for check in checks]
    overall = ("aligned" if "aligned" in statuses else
               "unrelated" if all(status == "unrelated" for status in statuses) else "uncertain")
    reason = ("至少一个目标有直接职责依据。" if overall == "aligned" else
              "所有目标均有明确否定或受保护非技术职能依据。" if overall == "unrelated" else
              "目标方向证据不足或存在冲突；未识别不等于无关。")
    return DirectionFit(status=overall, detected_directions=directions, reason=reason,
                        evidence=evidence, target_checks=checks)


_HEADINGS = {
    "bonus": r"加分项(?:目)?|加分条件|优先条件|优先考虑条件|优选条件|锦上添花|preferred qualifications|nice[- ]to[- ]haves?|bonus(?: skills)?",
    "core": r"任职要求|任职资格|岗位要求|职位要求|技能要求|必备技能|必备条件|基本要求|技术要求|required (?:qualifications|skills)|requirements|qualifications|must[- ]haves?",
    "duty": r"岗位职责|工作职责|岗位描述|职责描述|工作内容|职位描述|岗位内容|职责|responsibilities|job description",
    "other": r"职位福利|岗位福利|福利待遇|团队介绍|公司介绍|招聘流程|benefits|about us",
}
_HEADING = re.compile(r"(?:" + "|".join(f"(?P<{name}>{words})" for name, words in _HEADINGS.items())
                      + r")\s*(?:[:：]\s*|$)", re.I)
_CORE = re.compile(r"必须|必备|需要掌握|熟练|熟悉|掌握|精通|要求具备|须具备|\b(?:required|must|proficien(?:t|cy)|expertise|fluent)\b", re.I)
_BONUS = re.compile(r"优先|加分|更佳|最好|优选|\b(?:preferred|desirable|optional|bonus|nice[- ]to[- ]have|a plus)\b", re.I)
_AMBIGUOUS = re.compile(r"不(?:必|需|要求|强制|限于|限定|熟悉|熟练|掌握|会|是|属于|作为|负责|承担|涉及|参与|从事)|无需|无须|不限|并非|非(?:必[需须备]|硬性|强制)|无.{0,20}经验.{0,5}(?:可|也行)|或|任选|任意(?:一|两|二|多)|至少(?:一|1)种|二选一|其中之一|择一|\b(?:or|either|one of|not|no)\b", re.I)
_SENTENCE_END = re.compile(r"[。；;！!?？\r\n]+|(?<=[a-zA-Z])\.(?=\s|$)")
_BULLET = re.compile(r"^(?:[-•]\s+|\d{1,2}[、.)）-]\s*)")


@dataclass(frozen=True)
class _Clause:
    quote: EvidenceSpan
    section: str | None
    heading: EvidenceSpan | None


def _clauses(source: str) -> Iterator[_Clause]:
    section = None
    heading = None
    offset = 0
    for separator in _SENTENCE_END.finditer(source + "\n"):
        end = separator.start()
        raw = source[offset:end]
        start = offset
        offset = separator.end()
        text = raw.strip()
        if not text:
            continue
        start += raw.index(text)
        bullet = _BULLET.match(text)
        if bullet:
            start += bullet.end()
            text = source[start:end].strip()
        label = _HEADING.match(text)
        if label:
            section = label.lastgroup
            heading = _span("description", source, start, start + label.end())
            start += label.end()
            text = source[start:end].strip()
        if text:
            start = source.index(text, start, end)
            yield _Clause(_span("description", source, start, start + len(text)), section, heading)


_DIRECTION_SECTION = re.compile(
    r"(?:日常实习|ByteIntern|你将参与(?:的工作)?|你将负责|你的职责|你将做什么|你将参与|你可能会做什么)\s*(?:[:：]\s*|$)", re.I,
)


def _direction_clauses(source: str) -> Iterator[_Clause]:
    """Read task sections without changing the shared skill clause semantics.

    Recruiting templates may place a team introduction inside the duties block,
    then restart actual numbered tasks after a named internship introduction.
    Only an explicit section transition reopens those applicant duties.
    """
    section = None
    heading = None
    offset = 0
    for separator in _SENTENCE_END.finditer(source + "\n"):
        end = separator.start()
        raw = source[offset:end]
        start = offset
        offset = separator.end()
        text = raw.strip()
        if not text:
            continue
        start += raw.index(text)
        bullet = _BULLET.match(text)
        if bullet:
            start += bullet.end()
            text = source[start:end].strip()
        label = _HEADING.match(text)
        restart = _DIRECTION_SECTION.match(text)
        if label is not None or restart is not None:
            selected = label if label is not None else restart
            section = label.lastgroup if label is not None else "duty"
            heading = _span("description", source, start, start + selected.end())
            start += selected.end()
            text = source[start:end].strip()
        if text:
            start = source.index(text, start, end)
            yield _Clause(_span("description", source, start, start + len(text)), section, heading)


_DIRECTION_PREDICATE = re.compile(
    r"负责|承担|参与|开发|研发|构建|搭建|建设|设计和开发|设计和实现|不(?:再)?(?:负责|承担|涉及|参与|从事|做)|无需承担|不是|不属于|非",
)
_DIRECTION_CONJUNCTION = re.compile(r"\s*(?:(?:但是|然而|同时|此外|另外|但|并|且)\s*)*")
_NEGATIVE_SUBJECT = re.compile(r"(?:(?:本岗位|本职位|本岗|该岗位|该职位|你|您|实习生)\s*)?(?:(?:将|主要|独立)\s*)*")


def _direction_task_fragments(source: str) -> Iterator[_Clause]:
    """Keep whole task context and also expose independently stated predicates.

    This preserves generative-product context before a comma, while allowing a
    positive and a negative assignment in the same sentence to remain a conflict.
    Skill clause parsing is deliberately unchanged.
    """
    for clause in _direction_clauses(source):
        yield clause
        text = clause.quote.text
        cuts = []
        for comma in re.finditer(r"[,，]", text):
            start = _DIRECTION_CONJUNCTION.match(text, comma.end()).end()
            subject = _NEGATIVE_SUBJECT.match(text, start).end()
            if _DIRECTION_PREDICATE.match(text, subject):
                cuts.append((comma.start(), start))
        if not cuts:
            continue
        starts = [0, *(start for _, start in cuts)]
        ends = [*(end for end, _ in cuts), len(text)]
        for start, end in zip(starts, ends):
            part = text[start:end].strip()
            if not part:
                continue
            start = text.index(part, start, end)
            yield _Clause(_span("description", source, clause.quote.start + start,
                                clause.quote.start + start + len(part)), clause.section, clause.heading)


def _direction_denials(job: JobRead, targets: Sequence[TargetDirection]) -> dict[TargetDirection, list[EvidenceSpan]]:
    """Read explicit role denials, never infer a negative from another role."""
    result: dict[TargetDirection, list[EvidenceSpan]] = {}

    def record(text: str, quote: EvidenceSpan) -> None:
        subject = _NEGATIVE_SUBJECT.match(text).end()
        denial = _ROLE_DENIAL.match(text, subject)
        if denial is None:
            return
        denied_object = text[denial.end():]
        if not denied_object.strip() or _NON_ROLE_DENIAL.search(denied_object):
            return
        for target in targets:
            match = _NEGATIVE_ROLE_OBJECTS[target].search(denied_object)
            if match is not None and not _NON_ROLE_DENIAL_SUFFIX.match(denied_object, match.end()):
                quotes = result.setdefault(target, [])
                if quote not in quotes:
                    quotes.append(quote)

    for part in re.finditer(r"(?:^|[（）()，,;；/／])\s*([^（）()，,;；/／]+)", job.title):
        text = part.group(1).strip()
        record(text, _span("title", job.title, 0, len(job.title)))
    for clause in _direction_task_fragments(job.description):
        if clause.section in {"core", "bonus", "other"}:
            continue
        # A comma closes the object of an initial denial. A later independent
        # denial is evaluated through the fragment iterator above.
        text = re.split(r"[,，]", clause.quote.text, maxsplit=1)[0].strip()
        record(text, _span("description", job.description, clause.quote.start,
                           clause.quote.start + len(text)))
    return result


@lru_cache(maxsize=512)
def _skill_pattern(skill: str) -> re.Pattern:
    aliases = {skill, *(alias for alias, canonical in SKILL_ALIASES.items() if canonical.casefold() == skill.casefold())}
    words = [r"\s+".join(re.escape(token) for token in value.split()) for value in sorted(aliases, key=len, reverse=True)]
    return re.compile(r"(?<![a-zA-Z0-9_])(?:" + "|".join(words) + r")(?![a-zA-Z0-9_+#])", re.I)


def _skill_clauses(clause: _Clause) -> Iterator[_Clause]:
    """Split independent conditions at commas, keeping skill lists and alternatives together."""
    text = clause.quote.text
    if re.search(r"任选|至少(?:一|1)种|其中之一|任意一|\bone of\b", text, re.I):
        yield clause
        return
    start = 0
    for comma in re.finditer(r"[,，、]", text):
        left = text[start:comma.start()]
        following = text[comma.end():]
        right = re.split(r"[,，]", following, maxsplit=1)[0].strip()
        # A new predicate starts its own scope; a comma in a list does not.
        if not (re.match(r"(?:但|然而|but\b|且须|并须|熟悉|熟练|掌握|精通|要求|须|需具备|必须|有.+(?:经验|背景)|加分|优先|不要求|无需)", right, re.I)
                or (comma.group() != "、" and (_CORE.search(left) or _BONUS.search(left))
                    and (_CORE.search(right) or _BONUS.search(right)))):
            continue
        if left.strip():
            yield _subclause(clause, start, comma.start())
        start = comma.end()
    if text[start:].strip():
        yield _subclause(clause, start, len(text))


def _subclause(clause: _Clause, start: int, end: int) -> _Clause:
    sub = EvidenceSpan(field="description", text=clause.quote.text[start:end],
                       start=clause.quote.start + start, end=clause.quote.start + end)
    return _Clause(sub, clause.section, clause.heading)


def _strength(clause: _Clause, mentions: int) -> str:
    text = clause.quote.text
    if _AMBIGUOUS.search(text) or (mentions > 1 and re.search(r"[/／]", text)):
        return "ambiguous"
    if _BONUS.search(text) or clause.section == "bonus":
        return "bonus"
    if clause.section in {"duty", "other"}:
        return "mention"
    if re.search(r"(?:负责|参与|协助|将使用|工作中|we use|you will)", text, re.I):
        return "mention"
    if _CORE.search(text) or clause.section == "core":
        return "core"
    return "mention"


def classify_skill_requirements(job: JobRead, detected_skills: list[str], candidate_skills: list[str]) -> list[SkillRequirement]:
    patterns = [(skill, _skill_pattern(skill)) for skill in detected_skills]
    covered = {normalize_skill(skill).casefold() for skill in candidate_skills}
    observations: dict[str, list[tuple[str, list[EvidenceSpan]]]] = {skill: [] for skill in detected_skills}
    for clause in _clauses(job.description):
        for part in _skill_clauses(clause):
            present = [skill for skill, pattern in patterns if pattern.search(part.quote.text)]
            strength = _strength(part, len(present))
            quotes = [part.heading, part.quote] if part.heading is not None else [part.quote]
            for skill in present:
                observations[skill].append((strength, quotes))
    results = []
    for skill, pattern in patterns:
        mentions = observations[skill]
        strengths = {strength for strength, _ in mentions} - {"mention"}
        importance = next(iter(strengths)) if strengths in ({"core"}, {"bonus"}) else "unclassified"
        evidence = []
        for strength, quotes in mentions:
            if importance != "unclassified" and strength != importance:
                continue
            for quote in quotes:
                if quote not in evidence:
                    evidence.append(quote)
        if not evidence and pattern.search(job.title):
            evidence = [_span("title", job.title, 0, len(job.title))]
        results.append(SkillRequirement(skill=skill, importance=importance,
                                        matched=normalize_skill(skill).casefold() in covered, evidence=evidence))
    return results


# Ranking clues deliberately do not widen the direction classifier. A clear
# technical topic can support inspection order without resolving the role.
_SUPPORT_TITLE_EXCLUDED = re.compile(
    r"(?:品牌|视觉设计|平面设计|交互设计|设计师|公关|营销|运营|销售|产品经理|项目经理|UI\s*[/／]?\s*UX|\bUX\b)|"
    r"(?:团队|同事|背景|经验|优先)|不(?:负责|涉及|属于)|非", re.I,
)
_SUPPORT_TITLE: dict[TargetDirection, re.Pattern] = {
    "ai_application": re.compile(r"(?:Agent|智能体|RAG|(?:大模型|LLM|AI)\s*(?:应用|服务|工具集成|评测)).{0,20}(?:工程|研发|开发|实习)|(?:工程|研发|开发|评测).{0,20}(?:Agent|智能体|RAG|(?:大模型|LLM|AI)\s*(?:应用|服务|工具集成|评测))", re.I),
    "backend": re.compile(r"(?:后端|后台|服务端|backend).{0,20}(?:开发|研发|工程|实习)|(?:开发|研发|工程).{0,20}(?:后端|后台|服务端|backend)", re.I),
    "computer_vision": re.compile(r"(?:视觉|图像|图文|目标检测|图像分割|三维重建|深度估计|点云).{0,20}(?:算法|模型|研发|工程)|(?:算法|模型|研发|工程).{0,20}(?:视觉|图像|图文|目标检测|图像分割|三维重建|深度估计|点云)", re.I),
    "data": re.compile(r"(?:数据仓库|数仓|数据平台|数据工程|数据分析|数据挖掘|ETL).{0,20}(?:开发|研发|工程|分析|实习)|(?:开发|研发|工程).{0,20}(?:数据仓库|数仓|数据平台|ETL)", re.I),
    "frontend": re.compile(r"(?:前端|frontend|front-end).{0,20}(?:开发|研发|工程|实习)", re.I),
    "test_development": re.compile(r"(?:测试|自动化测试|QA|SDET).{0,20}(?:开发|研发|工程|实习)", re.I),
    "devops": re.compile(r"(?:DevOps|SRE|运维|持续集成).{0,20}(?:开发|研发|工程|实习)", re.I),
    "security": re.compile(r"(?:安全|security).{0,20}(?:开发|研发|工程|实习)", re.I),
}
_SUPPORT_ACTION = re.compile(r"开发|研发|构建|搭建|建设|实现|设计|部署|集成|接入|训练|优化|评测|研究", re.I)
_SUPPORT_NON_APPLICANT = re.compile(
    r"^(?:我们(?:的)?|本|该)?(?:公司|团队|部门|实验室|课题组)|"
    r"同事|团队负责|部门负责|团队讨论|团队研究|公司致力|团队致力|服务对象|曾经?|有过|历史|过去|"
    r"(?:与|和|协同|配合).{0,20}(?:团队|工程师|负责)|协助.{0,20}(?:同事|工程师|团队)|"
    r"不(?:必|需|要求|熟悉|掌握|强制|强求|负责|承担|涉及|参与|从事|限于)|无需|无须|不限|非必|优先|加分|"
    r"(?:无|没有).{0,20}经验.{0,8}(?:可|也行)|"
    r"(?:使用|运用|借助|利用).{0,15}(?:AI工具|人工智能工具|大模型工具|ChatGPT|Copilot)|"
    r"(?:使用|运用|借助|利用|调用).{0,15}(?:大模型|LLM|RAG|Agent|智能体).{0,30}(?:文案|材料|报告|办公|调研|绘图|策划|运营|营销|市场|创意|设计稿)|"
    r"\b(?:preferred|bonus|not|no)\b", re.I,
)
_SUPPORT_DUTY_START = re.compile(r"^(?:(?:本岗位|本职位|本岗|你|您|实习生)\s*)?(?:(?:将|主要|独立)\s*)*(?:负责|承担|参与|开发|研发|构建|搭建|建设|实现|设计|部署|集成|接入|优化|评测|研究)", re.I)
_SUPPORT_DUTY: dict[TargetDirection, re.Pattern] = {
    "ai_application": re.compile(r"(?:Agent|智能体|RAG|(?:大模型|LLM).{0,12}(?:应用|服务|工具|评测)|AI应用)", re.I),
    "backend": re.compile(r"后端|后台|服务端|(?:HTTP|REST(?:ful)?|RPC).{0,12}(?:服务|接口|API)|(?:API|接口).{0,12}(?:服务|系统|开发|研发|设计)|服务.{0,12}(?:API|接口)", re.I),
    "computer_vision": re.compile(r"(?:图像|视频|视觉|点云|三维).{0,16}(?:模型|算法|感知)|目标检测|图像分割|三维重建|深度估计|图文理解.{0,20}(?:Agent|智能体)|(?:Agent|智能体).{0,20}图文理解", re.I),
    "data": re.compile(r"数据仓库|数仓|数据管道|ETL|数据分析(?:模型|系统|平台)|数据挖掘", re.I),
    "frontend": re.compile(r"前端|(?:Web|网页).{0,12}(?:页面|交互|界面)", re.I),
    "test_development": re.compile(r"测试框架|测试平台|自动化测试|测试工具|测试用例", re.I),
    "devops": re.compile(r"CI/CD|持续集成|持续部署|运维平台|运维工具|部署流水线", re.I),
    "security": re.compile(r"安全平台|安全检测|漏洞检测|漏洞挖掘|入侵检测|渗透测试", re.I),
}
# These are ordering signals, not new recognized skills. General languages,
# SQL, PyTorch, Docker and Linux remain shared across several role families.
_SUPPORT_SKILLS: dict[TargetDirection, frozenset[str]] = {
    "ai_application": frozenset({"rag", "llm"}),
    "backend": frozenset({"fastapi"}),
    "computer_vision": frozenset({"opencv"}),
    "frontend": frozenset({"html"}),
}
_SUPPORT_SKILL_USAGE = re.compile(r"(?:使用|运用|借助|利用|操作).{0,12}(?:工具|平台)|(?:工具|平台)(?:的)?(?:使用|操作)|\b(?:use|using)\b", re.I)
_SUPPORT_ADMINISTRATIVE = re.compile(r"整理|编写|撰写|汇总|收集|宣传|推广|介绍|跟进|记录|沟通|协调|对接|组织|策划|销售|营销")
_SUPPORT_TASK_REFERENCE = re.compile(
    r"(?:开发|研发|设计|训练|研究|部署|集成)(?:工作)?(?:相关的?|的)?(?:宣传)?(?:文档|材料|报告|手册|指南|教程|说明)", re.I,
)


def _ranking_task_is_reference_only(text: str) -> bool:
    """Do not borrow a technical predicate from the material being handled.

    A real training/development task followed by experiment notes remains a
    technical task. In a documentation task, 'model development' names the
    subject of that document rather than an assignment to develop the model.
    """
    if _SUPPORT_TASK_REFERENCE.search(text):
        return True
    administrative = _SUPPORT_ADMINISTRATIVE.search(text)
    action = _SUPPORT_ACTION.search(text)
    return administrative is not None and (action is None or administrative.start() < action.start())


def evaluate_ranking_support(
    job: JobRead, targets: Sequence[TargetDirection], fit: DirectionFit,
    matched_skills: Sequence[str],
) -> RankingSupport:
    """Order uncertain candidates using bounded, individually quoted clues.

    This reads the source and existing positive observations; it never mutates
    fit, skill evidence, qualification decisions, or the retained candidate set.
    """
    if fit.status != "uncertain" or not targets:
        return RankingSupport(level="not_applicable", reason="本组沿用原有资格、方向及技能排序。")
    requested = list(dict.fromkeys(targets))
    # Conflicting positive/negative direction evidence needs clarification,
    # rather than a reward for repeating the positive half of that conflict.
    excluded_support = {check.target for check in fit.target_checks
                        if check.status == "unrelated" or (check.status == "uncertain" and check.evidence
                                                          and check.target in fit.detected_directions)}
    supported: list[TargetDirection] = []
    skills: list[str] = []
    evidence: list[EvidenceSpan] = []

    def add(target: TargetDirection, quote: EvidenceSpan, skill: str | None = None) -> None:
        if target not in supported:
            supported.append(target)
        if quote not in evidence:
            evidence.append(quote)
        if skill is not None and skill not in skills:
            skills.append(skill)

    if not _SUPPORT_TITLE_EXCLUDED.search(job.title):
        for target in requested:
            if target not in excluded_support and _SUPPORT_TITLE[target].search(job.title):
                add(target, _span("title", job.title, 0, len(job.title)))
    for clause in _direction_task_fragments(job.description):
        text = clause.quote.text
        if (clause.section in {"bonus", "other"} or _SUPPORT_NON_APPLICANT.search(text)
                or _ranking_task_is_reference_only(text)):
            continue
        duty = (clause.section != "core" and (clause.section == "duty" or _SUPPORT_DUTY_START.search(text))
                and _SUPPORT_ACTION.search(text))
        for target in requested:
            if target in excluded_support:
                continue
            if duty and _SUPPORT_DUTY[target].search(text):
                add(target, clause.quote)
            # A required specialized skill is useful for ordering even where
            # the exact engineering responsibility is still unresolved.
            mandatory = clause.section == "core" or _CORE.search(text)
            if not (mandatory or duty) or _SUPPORT_SKILL_USAGE.search(text):
                continue
            for skill in matched_skills:
                canonical = normalize_skill(skill).casefold()
                if canonical not in _SUPPORT_SKILLS.get(target, frozenset()):
                    continue
                if canonical == "llm" and not _SUPPORT_DUTY["ai_application"].search(text):
                    continue
                match = _skill_pattern(skill).search(text)
                if match is not None:
                    add(target, clause.quote, skill)
    if supported:
        labels = "、".join(_DIRECTION_NAMES[target] for target in requested if target in supported)
        return RankingSupport(level="target_specific", targets=[target for target in requested if target in supported],
                              matched_target_skills=[skill for skill in matched_skills if skill in skills],
                              reason=f"原文有{labels}的职责或已匹配专属技术线索，优先核对；方向仍待确认。",
                              evidence=evidence)
    other = [direction for direction in fit.detected_directions if direction not in requested]
    if other and not set(requested).intersection(fit.detected_directions) and fit.evidence:
        labels = "、".join(_DIRECTION_NAMES[direction] for direction in other)
        return RankingSupport(level="other_direction",
                              reason=f"目前明确线索指向{labels}，本次目标尚无专属支持；保留待确认并靠后核对。",
                              evidence=list(fit.evidence))
    return RankingSupport(level="insufficient", reason="未找到足够的目标专属排序线索，保留待确认；继续按原技能覆盖排序。")


def quality_rank_key(item) -> tuple:
    def coverage(importance: str) -> Fraction:
        skills = [entry for entry in item.skill_requirements if entry.importance == importance]
        return Fraction(sum(entry.matched for entry in skills), len(skills)) if skills else Fraction(-1)

    prefix = (0 if item.eligibility.overall == "met" else 1,
              1 if item.direction_fit.status == "uncertain" else 0)
    rest = (-coverage("core"), -coverage("bonus"), -item.match_score, -len(item.matched_skills), item.job.id)
    support = getattr(item, "ranking_support", None)
    if support is None:
        return (*prefix, *rest)
    level = {"target_specific": 0, "insufficient": 1, "other_direction": 2, "not_applicable": 0}[support.level]
    return (*prefix, level if item.direction_fit.status == "uncertain" else 0, *rest)
