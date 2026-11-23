"""Public recommendation scope and source provenance, independent of the backend."""

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field, StrictBool, model_validator

from demo.data_client import LibraryJob


class RecommendationDataScope(BaseModel):
    total_records: int = Field(strict=True, ge=0)
    sample_records_excluded: int = Field(strict=True, ge=0)
    duplicate_records_collapsed: int = Field(strict=True, ge=0)
    include_samples: StrictBool

    @model_validator(mode="after")
    def included_samples_cannot_be_excluded(self):
        if self.include_samples and self.sample_records_excluded:
            raise ValueError("Included samples cannot also be counted as excluded.")
        return self


class DuplicateSource(BaseModel):
    job_id: int = Field(strict=True, gt=0)
    source: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    status: Literal["active", "closed", "unknown"]
    last_checked_at: datetime | None = None
    updated_at: datetime | None = None
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)


class DuplicateGroup(BaseModel):
    primary_job_id: int = Field(strict=True, gt=0)
    sources: list[DuplicateSource] = Field(min_length=2)
    has_conflict: StrictBool
    selection_reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def primary_belongs_to_unique_sources(self):
        source_ids = [source.job_id for source in self.sources]
        if source_ids != sorted(set(source_ids)) or self.primary_job_id not in source_ids:
            raise ValueError("A duplicate group must contain its primary and distinct records.")
        identities = {_source_identity(source) for source in self.sources}
        if None in identities or len(identities) != 1:
            raise ValueError("Merged records must share a canonical URL, title, and company.")
        if len({source.status for source in self.sources}) > 1 and not self.has_conflict:
            raise ValueError("Different source statuses must disclose their conflict.")
        if not self.selection_reason.strip():
            raise ValueError("A duplicate group must explain its primary selection.")
        return self


def _source_identity(source: DuplicateSource) -> tuple[str, str, str] | None:
    # Mirror the public identity contract; no backend imports or fuzzy matching.
    try:
        parts = urlsplit(source.source_url.strip())
        scheme = parts.scheme.lower()
        if scheme not in {"http", "https"} or not parts.hostname:
            return None
        if parts.username is not None or parts.password is not None:
            return None
        host = parts.hostname.lower().rstrip(".")
        if ":" in host:
            host = f"[{host}]"
        port = parts.port
        if port is not None and (scheme, port) not in {("http", 80), ("https", 443)}:
            host += f":{port}"
        canonical = urlunsplit((scheme, host, parts.path or "/", parts.query, parts.fragment))
    except ValueError:
        return None
    company, title = (" ".join(value.split()).casefold() for value in (source.company, source.title))
    return (canonical, company, title) if company and title else None


def is_sample_record(source: str, source_url: str) -> bool:
    if source.strip().casefold() == "mock":
        return True
    try:
        hostname = (urlsplit(source_url.strip()).hostname or "").casefold().rstrip(".")
    except ValueError:
        return False
    return any(hostname == domain or hostname.endswith("." + domain)
               for domain in ("example.com", "example.org", "example.net"))


def validate_scope_provenance(
    scope: RecommendationDataScope | None, groups: list[DuplicateGroup],
    *, jobs: list[LibraryJob], evaluated: int,
) -> None:
    if scope is None:
        if groups:
            raise ValueError("Source groups require a validated data scope.")
        return
    if scope.total_records != (
        scope.sample_records_excluded + scope.duplicate_records_collapsed + evaluated
    ):
        raise ValueError("Data scope must account for every original record.")
    displayed = {job.id: job for job in jobs}
    if not scope.include_samples and any(
        is_sample_record(job.source, job.source_url) for job in jobs
    ):
        raise ValueError("Sample records must not appear in the real-job scope.")
    seen_ids: set[int] = set()
    shown_collapsed = 0
    for group in groups:
        job = displayed.get(group.primary_job_id)
        if job is None:
            raise ValueError("Source groups must belong to displayed recommendations or exclusions.")
        source_ids = {source.job_id for source in group.sources}
        if seen_ids & source_ids or (source_ids & displayed.keys()) != {group.primary_job_id}:
            raise ValueError("A source cannot be shared across groups or displayed twice.")
        seen_ids.update(source_ids)
        primary = next(source for source in group.sources if source.job_id == job.id)
        if any(getattr(primary, field) != getattr(job, field) for field in (
            "source", "source_url", "status", "last_checked_at", "updated_at", "title", "company"
        )):
            raise ValueError("Primary-source metadata must match the displayed job snapshot.")
        if not scope.include_samples and any(
            is_sample_record(source.source, source.source_url) for source in group.sources
        ):
            raise ValueError("Excluded sample sources must not enter duplicate groups.")
        shown_collapsed += len(group.sources) - 1
    if shown_collapsed > scope.duplicate_records_collapsed or (
        len(jobs) == evaluated and shown_collapsed != scope.duplicate_records_collapsed
    ):
        raise ValueError("Displayed source groups must agree with the collapsed-record count.")
