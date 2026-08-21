"""FastAPI dependencies for composing the agent application."""

import os
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agent.composition import create_agent_orchestrator
from app.agent.model_client import ModelClient
from app.agent.orchestrator import AgentOrchestrator
from app.agent.providers.deepseek_client import DeepSeekModelClient
from app.database.job_query_adapter import RepositoryJobQueryAdapter
from app.database.session import get_session


@lru_cache(maxsize=1)
def get_model_client() -> ModelClient:
    """Return the lazily constructed application-level model client."""

    api_key = os.getenv("DEEPSEEK_API_KEY")
    model = os.getenv("DEEPSEEK_MODEL")

    if (
        not api_key
        or not api_key.strip()
        or not model
        or not model.strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent model service is unavailable.",
        )

    return DeepSeekModelClient(
        model=model.strip(),
    )


def get_agent_orchestrator(
    session: Annotated[
        Session,
        Depends(get_session),
    ],
    model_client: Annotated[
        ModelClient,
        Depends(get_model_client),
    ],
) -> AgentOrchestrator:
    """Compose a request-scoped agent over the request database session."""

    job_query = RepositoryJobQueryAdapter(
        session=session,
    )

    return create_agent_orchestrator(
        model_client=model_client,
        job_query=job_query,
    )
