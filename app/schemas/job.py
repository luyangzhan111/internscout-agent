"""岗位数据的Pydantic模型。"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobCreate(BaseModel):
    """表示从招聘页面采集并清洗后的岗位数据。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(
        min_length=1,
        max_length=100,
        description="岗位名称",
    )
    company: str = Field(
        min_length=1,
        max_length=100,
        description="公司名称",
    )
    city: str = Field(
        min_length=1,
        max_length=50,
        description="工作城市",
    )
    salary: str | None = Field(
        default=None,
        max_length=100,
        description="薪资描述",
    )
    description: str = Field(
        min_length=1,
        description="岗位职责和要求",
    )
    skills: list[str] = Field(
        default_factory=list,
        description="岗位技能列表",
    )
    source: str = Field(
        min_length=1,
        max_length=50,
        description="数据来源",
    )
    source_url: str = Field(
        min_length=1,
        description="岗位原始链接",
    )
    source_job_id: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["active", "closed", "unknown"] = "unknown"
    published_at: date | None = Field(
        default=None,
        description="岗位发布日期",
    )

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        """Source names are case-insensitive; source job IDs are not."""

        return value.strip().lower()
