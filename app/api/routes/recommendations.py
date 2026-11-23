"""Authoritative skill/eligibility recommendations with optional Agent prose."""

from collections.abc import Callable
from functools import lru_cache
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAI
from sqlalchemy.orm import Session

from app.agent.model_client import ModelClient
from app.agent.recommendation_runtime import run_recommendation_explanation
from app.agent.providers.deepseek_client import DeepSeekModelClient
from app.database import get_session
from app.database.job_query_adapter import RepositoryJobQueryAdapter
from app.database.repository import get_dataset_revision
from app.recommendations.contracts import (
    AgentRecommendationResponse, RecommendationBatch, RecommendationCandidate,
    RecommendationRequest,
)
from app.recommendations.service import RecommendationService, build_recommendation_summary
from app.recommendations.explanation import parse_job_explanations


router = APIRouter(prefix="/api/agent", tags=["agent"])
ModelFactory = Callable[[], ModelClient | None]


@lru_cache(maxsize=1)
def _bounded_model(model: str, api_key: str) -> ModelClient:
    # Dedicated limits leave the legacy free-form query provider unchanged.
    # This is an HTTP phase timeout, not a strict end-to-end wall-clock budget.
    return DeepSeekModelClient(model=model, client=OpenAI(
        api_key=api_key, base_url="https://api.deepseek.com", timeout=8.0, max_retries=0,
    ))


def _optional_model() -> ModelClient | None:
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    model = os.getenv("DEEPSEEK_MODEL", "").strip()
    return _bounded_model(model, key) if key and model else None


def get_recommendation_model_factory() -> ModelFactory:
    # Defer even provider construction until input and rule results are ready.
    return _optional_model


def _stable_batch(
    session: Session,
    service: RecommendationService,
    candidate: RecommendationCandidate,
    limit: int,
    include_samples: bool = False,
) -> tuple[RecommendationBatch, int]:
    """Bounded retry across concurrent updates without holding a model-time read."""
    for _ in range(2):
        # This endpoint owns a read-only session. End a previous read snapshot
        # so another connection's committed edits are visible to the next scan.
        session.rollback()
        revision = get_dataset_revision(session)
        batch = service.recommend(candidate=candidate, limit=limit, include_samples=include_samples)
        session.rollback()
        if revision == get_dataset_revision(session):
            session.rollback()
            return batch, revision
    session.rollback()
    raise HTTPException(status_code=409, detail="岗位正在连续更新，请稍后重新推荐。")


@router.post(
    "/recommend", response_model=AgentRecommendationResponse,
    summary="结合目标岗位方向、技能要求与投递条件推荐岗位",
)
def recommend_jobs(
    request: RecommendationRequest,
    session: Annotated[Session, Depends(get_session)],
    model_factory: Annotated[ModelFactory, Depends(get_recommendation_model_factory)],
) -> AgentRecommendationResponse:
    service = RecommendationService(
        job_query=RepositoryJobQueryAdapter(session, include_closed=True),
    )
    try:
        batch, revision = _stable_batch(session, service, request.candidate, request.limit, request.include_samples)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="暂时无法读取当前岗位并生成推荐，请重试。") from exc

    explanation = None
    job_explanations = []
    steps = tool_count = 0
    if not request.explain_with_model:
        explanation_status = "disabled"
        notice = "本次仅展示规则推荐，未请求 AI 补充说明。"
    elif not batch.recommendations:
        explanation_status = "not_needed"
        notice = "本次没有可推荐岗位，未调用模型；请查看数据范围及排除原因。"
    else:
        try:
            model_client = model_factory()
            if model_client is None:
                explanation_status = "unavailable"
                notice = "未配置 AI 模型，以下技能与投递条件结果已由规则完成。"
            else:
                steps = tool_count = None
                result = run_recommendation_explanation(model_client, request.candidate, batch)
                explanation = result.answer
                steps, tool_count = result.steps, len(result.tool_executions)
                explanation_status = "generated"
                notice = "AI 说明仅供参考；岗位顺序、技能分数和投递条件以规则卡片为准。"
                try:
                    job_explanations = parse_job_explanations(
                        explanation, [item.job.id for item in batch.recommendations]
                    )
                except ValueError:
                    # Keep the original response for older clients, without
                    # treating malformed or mismatched prose as per-job facts.
                    notice = "AI 补充说明未能按岗位整理；推荐条件和依据仍以规则卡片为准。"
        except Exception:
            explanation_status = "failed"
            notice = "AI 补充说明暂未完成，规则推荐结果仍可使用。"

    # Observation timestamps can change without a content revision, and now
    # affect which duplicate source is primary. Recheck both version and values.
    try:
        latest, latest_revision = _stable_batch(
            session, service, request.candidate, request.limit, request.include_samples
        )
        if latest_revision != revision or latest.model_dump(exclude={"assessed_at"}) != batch.model_dump(exclude={"assessed_at"}):
            batch = latest
            had_explanation = explanation is not None or bool(job_explanations)
            explanation = None
            job_explanations = []
            if had_explanation:
                explanation_status = "stale"
                notice = "本次请求期间岗位来源信息已更新；已重新判断，旧说明已舍弃。"
            elif explanation_status == "not_needed":
                notice = "岗位来源信息已更新，已重新判断；本次未调用模型，需要新说明请重新获取推荐。"
            else:
                notice = "本次请求期间岗位来源信息已更新，已重新判断。" + notice
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="无法确认岗位的最新状态，请重新推荐。") from exc

    return AgentRecommendationResponse(
        **batch.model_dump(), summary=build_recommendation_summary(batch),
        model_explanation=explanation, explanation_status=explanation_status,
        job_explanations=job_explanations,
        explanation_notice=notice, steps=steps, tool_execution_count=tool_count,
    )
