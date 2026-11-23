"""Validated, model-independent input and output for the job library."""

from datetime import date, datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.schemas.job import JobCreate


class ManualJobInput(BaseModel):
    """A pasted job description; the caller cannot impersonate a crawler."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=100)
    company: str = Field(min_length=1, max_length=100)
    city: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1, max_length=50000)
    source_url: HttpUrl = Field(max_length=2048)
    source_job_id: str | None = Field(default=None, min_length=1, max_length=200)
    salary: str | None = Field(default=None, max_length=100)
    skills: list[str] = Field(default_factory=list, max_length=100)
    published_at: date | None = None
    status: Literal["active", "closed", "unknown"] = "unknown"

    @field_validator("source_url")
    @classmethod
    def reject_credentials(cls, value: HttpUrl) -> HttpUrl:
        parts = urlsplit(str(value))
        if parts.username is not None or parts.password is not None:
            raise ValueError("岗位来源链接不能包含账号或密码。")
        return value

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 100 for value in values):
            raise ValueError("技能不能为空且每项不能超过 100 个字符。")
        return values

    def to_job(self) -> JobCreate:
        data = self.model_dump()
        data["source_url"] = str(self.source_url)
        return JobCreate(source="manual", **data)


class ManualImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jobs: list[ManualJobInput] = Field(min_length=1, max_length=100)


class OppoRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    keyword: str = Field(default="", max_length=100)
    max_pages: int = Field(default=2, ge=1, le=10, strict=True)
    max_jobs: int = Field(default=20, ge=1, le=100, strict=True)


class IngestionError(BaseModel):
    item_id: str | None = None
    message: str


class IngestionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    status: Literal["running", "succeeded", "partial", "failed"]
    started_at: datetime
    finished_at: datetime | None = None
    created_count: int = Field(ge=0)
    updated_count: int = Field(ge=0)
    unchanged_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    complete: bool
    errors: list[IngestionError]
    warnings: list[str] = Field(default_factory=list)
    job_ids: list[int]
