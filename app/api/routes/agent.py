"""Agent query API route."""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from app.agent.orchestrator import AgentOrchestrator
from app.api.dependencies import get_agent_orchestrator
from app.schemas import (
    AgentQueryRequest,
    AgentQueryResponse,
)


router = APIRouter(
    prefix="/api/agent",
    tags=["agent"],
)


@router.post(
    "/query",
    response_model=AgentQueryResponse,
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
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent service encountered an unexpected error.",
        ) from exc
