"""Read-only, model-independent application eligibility checks."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_job_by_id, get_session
from app.eligibility.contracts import EligibilityRequest, EligibilityResponse
from app.eligibility.evaluator import evaluate_eligibility
from app.schemas.job_response import JobRead


router = APIRouter(prefix="/api/eligibility", tags=["eligibility"])


@router.post(
    "/evaluate",
    response_model=EligibilityResponse,
    summary="根据当前岗位原文检查五类投递条件",
)
def evaluate_jobs(
    request: EligibilityRequest,
    session: Annotated[Session, Depends(get_session)],
) -> EligibilityResponse:
    # Load every requested job before evaluating. Never silently omit unknown IDs
    # or substitute an older result; candidate inputs are not persisted.
    jobs = [get_job_by_id(session, job_id) for job_id in request.job_ids]
    missing = [job_id for job_id, job in zip(request.job_ids, jobs) if job is None]
    if missing:
        raise HTTPException(
            status_code=404,
            detail="岗位不存在：" + "、".join(map(str, missing)),
        )
    return EligibilityResponse(
        items=[evaluate_eligibility(JobRead.model_validate(job), request.profile) for job in jobs],
        assessed_at=datetime.now(timezone.utc),
    )
