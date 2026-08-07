"""岗位查询API路由。"""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy.orm import Session

from app.database import (
    get_session,
    query_jobs,
)
from app.schemas import (
    JobListResponse,
    JobRead,
)


router = APIRouter(
    prefix="/api/jobs",
    tags=["jobs"],
)


def _normalize_optional_query(
    value: str | None,
    parameter_name: str,
) -> str | None:
    """清理可选查询参数，并拒绝纯空白值。"""

    if value is None:
        return None

    normalized = " ".join(value.split())

    if not normalized:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{parameter_name}"
                "不能只包含空白字符"
            ),
        )

    return normalized


@router.get(
    "",
    response_model=JobListResponse,
    summary="查询岗位列表",
)
def read_jobs(
    session: Annotated[
        Session,
        Depends(get_session),
    ],
    city: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=50,
            description="按城市精确筛选",
        ),
    ] = None,
    company: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=100,
            description="按公司名称精确筛选",
        ),
    ] = None,
    skill: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=100,
            description="按技能名称精确筛选",
        ),
    ] = None,
    page: Annotated[
        int,
        Query(
            ge=1,
            description="页码，从1开始",
        ),
    ] = 1,
    page_size: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="每页岗位数量",
        ),
    ] = 10,
) -> JobListResponse:
    """按照筛选条件分页查询数据库岗位。"""

    normalized_city = _normalize_optional_query(
        city,
        "city",
    )
    normalized_company = _normalize_optional_query(
        company,
        "company",
    )
    normalized_skill = _normalize_optional_query(
        skill,
        "skill",
    )

    database_jobs, total = query_jobs(
        session,
        city=normalized_city,
        company=normalized_company,
        skill=normalized_skill,
        page=page,
        page_size=page_size,
    )

    pages = (
        (total + page_size - 1) // page_size
        if total > 0
        else 0
    )

    response_items = [
        JobRead.model_validate(database_job)
        for database_job in database_jobs
    ]

    return JobListResponse(
        items=response_items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )
