"""Model-independent job import and bounded source-refresh endpoints."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crawlers.contracts import CrawlBatch
from app.crawlers.oppo_crawler import OppoJobCrawler
from app.crawlers.oppo_source_client import OppoJobSourceClient
from app.database.ingestion_models import IngestionRunModel
from app.database.session import get_session
from app.schemas.ingestion import (
    IngestionRunRead,
    ManualImportRequest,
    OppoRefreshRequest,
)
from app.workflows.real_job_ingestion import import_job_batch


router = APIRouter(prefix="/api/imports", tags=["imports"])
OppoBatchFetcher = Callable[[OppoRefreshRequest], CrawlBatch]


def fetch_oppo_batch(request: OppoRefreshRequest) -> CrawlBatch:
    """Only the fixed OPPO adapter performs network requests."""

    with httpx.Client(follow_redirects=False) as http_client:
        source_client = OppoJobSourceClient(http_client, timeout=5.0)
        crawler = OppoJobCrawler(
            source_client,
            keyword=request.keyword,
            max_pages=request.max_pages,
            max_jobs=request.max_jobs,
        )
        return crawler.fetch_batch()


def get_oppo_batch_fetcher() -> OppoBatchFetcher:
    """Inject the source boundary for deterministic integration tests."""

    return fetch_oppo_batch


@router.post("/manual", response_model=IngestionRunRead, summary="导入或更新手动岗位")
def import_manual_jobs(
    request: ManualImportRequest,
    session: Annotated[Session, Depends(get_session)],
) -> IngestionRunRead:
    jobs = [item.to_job() for item in request.jobs]
    run = import_job_batch(
        session,
        source="manual",
        fetch=lambda: CrawlBatch(jobs=jobs, failures=[], complete=True),
    )
    return IngestionRunRead.model_validate(run)


@router.post("/oppo", response_model=IngestionRunRead, summary="按需刷新 OPPO 岗位")
def refresh_oppo_jobs(
    request: OppoRefreshRequest,
    session: Annotated[Session, Depends(get_session)],
    fetcher: Annotated[OppoBatchFetcher, Depends(get_oppo_batch_fetcher)],
) -> IngestionRunRead:
    run = import_job_batch(session, source="oppo", fetch=lambda: fetcher(request))
    return IngestionRunRead.model_validate(run)


@router.get("", response_model=list[IngestionRunRead], summary="查看最近导入与刷新")
def read_import_runs(
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[IngestionRunRead]:
    runs = session.scalars(select(IngestionRunModel).order_by(IngestionRunModel.id.desc()).limit(limit))
    return [IngestionRunRead.model_validate(run) for run in runs]


@router.get("/{run_id}", response_model=IngestionRunRead, summary="查看导入与刷新详情")
def read_import_run(
    run_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> IngestionRunRead:
    run = session.get(IngestionRunModel, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="导入记录不存在。")
    return IngestionRunRead.model_validate(run)
