"""Explicit outcomes for bounded source refreshes."""

from dataclasses import dataclass, field

from app.schemas.job import JobCreate


@dataclass(frozen=True, slots=True)
class CrawlFailure:
    """A safe, user-facing failure without transport or credential details."""

    item_id: str | None
    message: str


@dataclass(frozen=True, slots=True)
class CrawlBatch:
    """Successful jobs plus an honest description of refresh coverage."""

    jobs: list[JobCreate]
    failures: list[CrawlFailure]
    complete: bool
    warnings: list[str] = field(default_factory=list)
