"""HTTP contracts and client for the model-independent job library."""

import os
import re
from datetime import date, datetime
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from demo.client import (
    API_BASE_URL_ENV,
    API_TIMEOUT_ENV,
    DEFAULT_API_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    BackendRequestError,
    BackendResponseError,
    BackendTimeoutError,
    BackendUnavailableError,
)


JobStatus = Literal["active", "closed", "unknown"]


class LibraryJob(BaseModel):
    """Public job fields used by the library; no database access is needed."""

    model_config = ConfigDict(extra="ignore")

    id: int
    title: str
    company: str
    city: str
    description: str
    source: str
    source_url: str
    source_job_id: str | None = None
    salary: str | None = None
    skills: list[str] = Field(default_factory=list)
    published_at: date | None = None
    status: JobStatus = "unknown"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_seen_at: datetime | None = None
    last_checked_at: datetime | None = None


class JobLibraryPage(BaseModel):
    items: list[LibraryJob]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    pages: int = Field(ge=0)


class SampleLoadResult(BaseModel):
    processed_count: int = Field(ge=0)


class ImportErrorDetail(BaseModel):
    item_id: str | None = None
    message: str


class ImportRun(BaseModel):
    """An HTTP 200 may still describe a failed or incomplete operation."""

    model_config = ConfigDict(extra="ignore")

    id: int
    source: Literal["manual", "oppo"]
    status: Literal["running", "succeeded", "partial", "failed"]
    started_at: datetime
    finished_at: datetime | None = None
    created_count: int = Field(ge=0)
    updated_count: int = Field(ge=0)
    unchanged_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    complete: bool
    errors: list[ImportErrorDetail] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    job_ids: list[int] = Field(default_factory=list)


def safe_http_url(value: str | None) -> str | None:
    """Only allow ordinary HTTP(S) links in user-facing source buttons."""

    if not value:
        return None
    normalized = value.strip()
    if not normalized or any(
        character.isspace() or ord(character) < 32
        for character in normalized
    ) or "\\" in normalized:
        return None
    try:
        parsed = urlsplit(normalized)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return None
        # Accessing port also validates malformed ports.
        parsed.port
    except ValueError:
        return None
    return normalized


def build_manual_import_payload(
    *,
    title: str,
    company: str,
    city: str,
    description: str,
    source_url: str,
    source_job_id: str = "",
    salary: str = "",
    skills_text: str = "",
    published_at: str = "",
    status: JobStatus = "unknown",
) -> dict[str, Any]:
    """Normalize a pasted job without inventing missing source evidence."""

    required = {
        "title": (title, "岗位名称"),
        "company": (company, "公司"),
        "city": (city, "城市"),
        "description": (description, "岗位原文"),
    }
    job: dict[str, Any] = {}
    for field, (value, label) in required.items():
        if not value.strip():
            raise ValueError(f"请填写{label}。")
        job[field] = value.strip()

    link = safe_http_url(source_url)
    if link is None:
        raise ValueError("请填写有效的 http:// 或 https:// 岗位来源链接。")
    if status not in {"active", "closed", "unknown"}:
        raise ValueError("请选择有效的岗位状态。")
    job.update(source_url=link, status=status)
    if source_job_id.strip():
        job["source_job_id"] = source_job_id.strip()
    if salary.strip():
        job["salary"] = salary.strip()
    job["skills"] = list(dict.fromkeys(
        part.strip()
        for part in re.split(r"[,，、\n]", skills_text)
        if part.strip()
    ))
    if published_at.strip():
        try:
            job["published_at"] = date.fromisoformat(
                published_at.strip()
            ).isoformat()
        except ValueError as exc:
            raise ValueError("发布日期请使用 YYYY-MM-DD 格式，未知可留空。") from exc
    return {"jobs": [job]}


class JobDataApiClient:
    """Browse and maintain jobs through public HTTP endpoints only."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_API_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.strip().rstrip("/")
        if not self._base_url:
            raise ValueError("岗位服务地址不能为空。")
        if timeout_seconds <= 0:
            raise ValueError("请求超时时间必须大于零。")
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    @classmethod
    def from_env(cls) -> "JobDataApiClient":
        try:
            timeout = float(os.getenv(
                API_TIMEOUT_ENV, str(DEFAULT_TIMEOUT_SECONDS)
            ))
        except ValueError as exc:
            raise ValueError("岗位服务的超时时间配置无效。") from exc
        return cls(
            base_url=os.getenv(API_BASE_URL_ENV, DEFAULT_API_BASE_URL),
            timeout_seconds=timeout,
        )

    def list_jobs(
        self,
        *,
        source: str | None = None,
        status: JobStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> JobLibraryPage:
        params: dict[str, str | int] = {"page": page, "page_size": page_size}
        if source:
            params["source"] = source
        if status:
            params["status"] = status
        return self._read(
            "GET", "/api/jobs", JobLibraryPage, params=params
        )

    def import_manual(self, payload: dict[str, Any]) -> ImportRun:
        return self._read(
            "POST", "/api/imports/manual", ImportRun, json=payload
        )

    def load_samples(self) -> SampleLoadResult:
        return self._read("POST", "/api/crawl", SampleLoadResult)

    def refresh_oppo(
        self, *, keyword: str = "", max_pages: int = 2, max_jobs: int = 20
    ) -> ImportRun:
        return self._read(
            "POST",
            "/api/imports/oppo",
            ImportRun,
            json={
                "keyword": keyword.strip(),
                "max_pages": max_pages,
                "max_jobs": max_jobs,
            },
        )

    def list_imports(self, *, limit: int = 10) -> list[ImportRun]:
        return self._read(
            "GET", "/api/imports", list[ImportRun], params={"limit": limit}
        )

    def _read(self, method: str, path: str, contract: Any, **kwargs: Any) -> Any:
        try:
            with httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            message = "岗位服务响应超时，请稍后重试。"
            if path.startswith("/api/imports/") and method == "POST":
                message = "等待导入结果超时；操作可能仍在进行，请先查看近期记录，避免重复提交。"
            raise BackendTimeoutError(message) from exc
        except httpx.RequestError as exc:
            raise BackendUnavailableError("暂时无法连接岗位服务，请确认后端已启动。") from exc

        if response.status_code >= 500:
            raise BackendUnavailableError("岗位服务暂时不可用，请稍后重试。")
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
            if not isinstance(detail, str) or not detail.strip():
                detail = f"岗位服务未接受请求（HTTP {response.status_code}），请检查填写内容。"
            raise BackendRequestError(detail)
        try:
            return TypeAdapter(contract).validate_python(response.json())
        except (ValueError, ValidationError) as exc:
            raise BackendResponseError("岗位服务返回了无法读取的结果，请检查后端版本。") from exc
