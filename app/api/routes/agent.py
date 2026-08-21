"""Agent query API route."""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from app.agent.contracts import AgentResult
from app.agent.orchestrator import AgentOrchestrator
from app.api.dependencies import get_agent_orchestrator
from app.matching.contracts import JobMatchResult
from app.schemas import (
    AgentQueryRequest,
    AgentQueryResponse,
)


router = APIRouter(
    prefix="/api/agent",
    tags=["agent"],
)


def _project_recommendations(
    result: AgentResult,
) -> list[JobMatchResult]:
    """Project the latest successful match_jobs result for the API."""

    for execution in reversed(result.tool_executions):
        tool_result = execution.result

        if (
            tool_result.tool_name != "match_jobs"
            or not tool_result.success
        ):
            continue

        if not isinstance(tool_result.data, list):
            raise ValueError(
                "The match_jobs result must be a list."
            )

        return [
            JobMatchResult.model_validate(item)
            for item in tool_result.data
        ]

    return []


@router.post(
    "/query",
    response_model=AgentQueryResponse,
    response_model_exclude_none=True,
    summary="Run an agent query",
)
def query_agent(
    request: AgentQueryRequest,
    orchestrator: Annotated[
        AgentOrchestrator,
        Depends(get_agent_orchestrator),
    ],
) -> AgentQueryResponse:
    """Run one independent agent query."""

    try:
        result = orchestrator.run(
            request.user_message
        )

        return AgentQueryResponse(
            answer=result.answer,
            steps=result.steps,
            tool_execution_count=len(
                result.tool_executions
            ),
            recommendations=(
                _project_recommendations(result)
                if request.include_recommendations
                else None
            ),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent service encountered an unexpected error.",
        ) from exc
