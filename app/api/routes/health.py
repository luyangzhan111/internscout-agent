"""服务健康检查API路由。"""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_session
from app.schemas import HealthResponse


router = APIRouter(
    prefix="/api",
    tags=["health"],
)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="检查服务和数据库状态",
    responses={
        503: {
            "description": "数据库不可用",
        },
    },
)
def health_check(
    session: Annotated[
        Session,
        Depends(get_session),
    ],
) -> HealthResponse:
    """检查FastAPI服务及数据库连接是否可用。"""

    try:
        session.execute(
            text("SELECT 1")
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="数据库不可用",
        ) from exc

    return HealthResponse(
        status="ok",
        database="ok",
    )
