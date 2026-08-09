"""岗位采集API路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.crawlers import MockJobCrawler
from app.database import (
    get_session,
    query_jobs,
)
from app.schemas import CrawlResponse
from app.workflows import ingest_jobs


router = APIRouter(
    prefix="/api",
    tags=["crawl"],
)


@router.post(
    "/crawl",
    response_model=CrawlResponse,
    summary="采集模拟岗位",
)
def crawl_jobs(
    session: Annotated[
        Session,
        Depends(get_session),
    ],
) -> CrawlResponse:
    """采集、清洗、去重并保存模拟岗位。"""

    processed_jobs = ingest_jobs(
        MockJobCrawler(),
        session,
    )

    _, database_total = query_jobs(
        session,
        page=1,
        page_size=1,
    )

    return CrawlResponse(
        processed_count=len(processed_jobs),
        database_total=database_total,
    )
