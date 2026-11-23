"""Conservative read-time grouping; source records are never changed or deleted."""

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from app.schemas.job_response import JobRead
from app.services.deduplicator import canonical_job_url
from app.services.skill_vocabulary import normalize_skills


_EXAMPLE_DOMAINS = ("example.com", "example.org", "example.net")


def is_sample_source(source: str, source_url: str) -> bool:
    if source.strip().casefold() == "mock":
        return True
    try:
        host = (urlsplit(source_url.strip()).hostname or "").casefold().rstrip(".")
    except ValueError:
        return False
    return any(host == domain or host.endswith("." + domain) for domain in _EXAMPLE_DOMAINS)


def is_sample_record(job: JobRead) -> bool:
    return is_sample_source(job.source, job.source_url)


def _normalized_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def canonical_identity(source_url: str, company: str, title: str) -> tuple[str, str, str] | None:
    """Keep path/query identity; malformed or credential-bearing URLs never merge."""
    try:
        original_fragment = urlsplit(source_url.strip()).fragment
        url = canonical_job_url(source_url)
        parts = urlsplit(url)
        # A DNS terminal dot does not distinguish jobs; path/query stay exact.
        host = (parts.hostname or "").rstrip(".")
        if ":" in host:
            host = f"[{host}]"
        netloc = host + (f":{parts.port}" if parts.port is not None else "")
        # A hash can be a SPA route or a job identifier. Keeping every nonempty
        # fragment is safer than collapsing different positions as page anchors.
        canonical = urlunsplit((parts.scheme, netloc, parts.path, parts.query, original_fragment))
    except (ValueError, TypeError):
        return None
    normalized_company, normalized_title = _normalized_name(company), _normalized_name(title)
    if not normalized_company or not normalized_title:
        return None
    return canonical, normalized_company, normalized_title


def _official_oppo(job: JobRead) -> bool:
    try:
        host = (urlsplit(job.source_url).hostname or "").casefold().rstrip(".")
    except ValueError:
        return False
    return job.source.strip().casefold() == "oppo" and host == "career.oppo.com"


def _available_time(job: JobRead) -> datetime:
    values = [value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
              for value in (job.last_checked_at, job.updated_at) if value is not None]
    return max(values) if values else datetime.min.replace(tzinfo=timezone.utc)


def _content_signature(job: JobRead) -> tuple:
    return (
        job.description.replace("\r\n", "\n"), job.city, job.salary,
        tuple(sorted(skill.casefold() for skill in normalize_skills(job.skills))), job.status,
    )


@dataclass(frozen=True, slots=True)
class JobSourceGroup:
    primary: JobRead
    records: tuple[JobRead, ...]
    has_conflict: bool
    selection_reason: str


def group_jobs(jobs: list[JobRead]) -> list[JobSourceGroup]:
    grouped: dict[tuple, list[JobRead]] = {}
    for job in jobs:
        identity = canonical_identity(job.source_url, job.company, job.title)
        key = ("canonical", *identity) if identity is not None else ("unmergeable", job.id)
        grouped.setdefault(key, []).append(job)
    groups: list[JobSourceGroup] = []
    for records in grouped.values():
        primary = max(records, key=lambda job: (
            _official_oppo(job), _available_time(job), job.status == "closed", -job.id,
        ))
        reason = (
            "优先采用已接入的 OPPO 官网来源；同级来源按可用记录时间、关闭状态和岗位编号稳定选择。"
            if _official_oppo(primary) else
            "按最近核对或内容更新时间选择；时间相同时优先保留关闭状态，再按岗位编号稳定选择。"
        )
        groups.append(JobSourceGroup(
            primary=primary, records=tuple(sorted(records, key=lambda job: job.id)),
            has_conflict=len({_content_signature(job) for job in records}) > 1,
            selection_reason=reason,
        ))
    return sorted(groups, key=lambda group: group.primary.id)
