"""岗位数据唯一标识与去重。"""

from app.schemas.job import JobCreate
from app.services.cleaner import normalize_city
from urllib.parse import urlsplit, urlunsplit


JobIdentity = tuple[str, ...]


def canonical_job_url(value: str) -> str:
    """Normalize HTTP origin spelling, preserving path, query and SPA routes."""

    parts = urlsplit(value.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("source_url must be an absolute HTTP(S) URL")
    if parts.username is not None or parts.password is not None:
        raise ValueError("source_url must not contain credentials")
    host = parts.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    port = parts.port  # Also reject malformed ports.
    scheme = parts.scheme.lower()
    if port is not None and (scheme, port) not in {("http", 80), ("https", 443)}:
        host = f"{host}:{port}"
    return urlunsplit((scheme, host, parts.path or "/", parts.query, parts.fragment))


def normalize_identity_text(value: str) -> str:
    """清理用于身份比较的文本，并忽略大小写差异。"""

    return " ".join(value.split()).casefold()


def build_job_identity(job: JobCreate) -> JobIdentity:
    """
    优先按来源内稳定 ID 识别岗位，其次按来源内 URL。

    manual 导入来自多个站点，来源 ID 仅为元数据，始终按 URL 识别。
    只有没有来源 ID 的 mock 数据保留旧演示的公司、名称、城市策略。
    不同来源的岗位不会被静默合并；来源 ID 保留大小写。
    """

    source = job.source.strip().lower()
    if source == "manual":
        return ("v2", "source_url", source, canonical_job_url(job.source_url))
    if job.source_job_id is not None:
        return ("v2", "source_id", source, job.source_job_id)
    if source != "mock":
        return ("v2", "source_url", source, canonical_job_url(job.source_url))
    return (
        normalize_identity_text(job.company),
        normalize_identity_text(job.title),
        normalize_identity_text(normalize_city(job.city)),
    )


def deduplicate_jobs(jobs: list[JobCreate]) -> list[JobCreate]:
    """按岗位唯一标识去重，并保留第一次出现的顺序。"""

    unique_jobs: list[JobCreate] = []
    seen: set[JobIdentity] = set()

    for job in jobs:
        identity = build_job_identity(job)

        if identity in seen:
            continue

        seen.add(identity)
        unique_jobs.append(job)

    return unique_jobs
