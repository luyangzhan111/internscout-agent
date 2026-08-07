"""岗位查询API响应模型。"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class JobRead(BaseModel):
    """对外返回的岗位信息。"""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    title: str
    company: str
    city: str
    salary: str | None
    description: str
    skills: list[str]
    source: str
    source_url: str
    published_at: date | None
    created_at: datetime


class JobListResponse(BaseModel):
    """带分页信息的岗位列表响应。"""

    items: list[JobRead]
    total: int = Field(
        ge=0,
        description="符合查询条件的岗位总数",
    )
    page: int = Field(
        ge=1,
        description="当前页码",
    )
    page_size: int = Field(
        ge=1,
        le=100,
        description="每页岗位数量",
    )
    pages: int = Field(
        ge=0,
        description="总页数",
    )
