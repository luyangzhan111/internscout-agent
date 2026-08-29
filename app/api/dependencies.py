"""FastAPI dependencies for composing the agent application."""

import os
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.agent.composition import create_agent_orchestrator
from app.agent.tools.job_query import JobQueryPort
from app.agent.model_client import ModelClient
from app.agent.orchestrator import AgentOrchestrator
from app.agent.providers.deepseek_client import DeepSeekModelClient
from app.database.job_query_adapter import RepositoryJobQueryAdapter
from app.database.session import get_session
from app.rag.embedding import OpenAICompatibleEmbeddingProvider
from app.rag.retriever import JobKnowledgeRetriever
from app.rag.runtime import RetrievalRuntime
from app.schemas.job_response import JobRead


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


def create_retrieval_runtime() -> RetrievalRuntime | None:
    """Create the optional application-level retrieval runtime.

    Retrieval is enabled only when its connection credentials are configured.
    Provider construction does not perform an embedding request; indexing is
    deferred until an Agent request actually needs retrieval.
    """

    api_key = os.getenv("INTERNSCOUT_EMBEDDING_API_KEY")
    base_url = os.getenv("INTERNSCOUT_EMBEDDING_BASE_URL")

    if (
        not api_key
        or not api_key.strip()
        or not base_url
        or not base_url.strip()
    ):
        return None

    try:
        embedding_provider = OpenAICompatibleEmbeddingProvider(
            api_key=api_key.strip(),
            base_url=base_url.strip(),
        )
    except ValueError:
        # Invalid optional RAG configuration must not prevent the core app
        # and non-RAG Agent tools from starting.
        return None

    return RetrievalRuntime(
        embedding_provider=embedding_provider,
    )


def get_retrieval_runtime(
    request: Request,
) -> RetrievalRuntime | None:
    """Return the application-scoped retrieval runtime, if enabled."""

    return getattr(
        request.app.state,
        "retrieval_runtime",
        None,
    )


def _collect_all_jobs(
    job_query: JobQueryPort,
) -> list[JobRead]:
    """Collect the complete job snapshot through the existing query port."""

    jobs: list[JobRead] = []
    page = 1

    while True:
        page_jobs, total = job_query.search_jobs(
            page=page,
            page_size=100,
        )
        jobs.extend(page_jobs)

        if not page_jobs or len(jobs) >= total:
            return jobs

        page += 1


def _get_request_retriever(
    runtime: RetrievalRuntime | None,
    job_query: JobQueryPort,
) -> JobKnowledgeRetriever | None:
    """Return a ready retriever, rebuilding lazily when the index is stale."""

    if runtime is None:
        return None

    if runtime.is_dirty or not runtime.is_ready:
        try:
            runtime.rebuild(
                _collect_all_jobs(job_query)
            )
        except Exception:
            # Retrieval is optional.  A previous complete index remains a
            # safe fallback; a first-build failure leaves retrieval disabled.
            return runtime.current_retriever

    return runtime.current_retriever


def get_agent_orchestrator(
    session: Annotated[
        Session,
        Depends(get_session),
    ],
    model_client: Annotated[
        ModelClient,
        Depends(get_model_client),
    ],
    retrieval_runtime: Annotated[
        RetrievalRuntime | None,
        Depends(get_retrieval_runtime),
    ],
) -> AgentOrchestrator:
    """Compose a request-scoped agent over the request database session."""

    job_query = RepositoryJobQueryAdapter(
        session=session,
    )
    job_retriever = _get_request_retriever(
        retrieval_runtime,
        job_query,
    )

    return create_agent_orchestrator(
        model_client=model_client,
        job_query=job_query,
        job_retriever=job_retriever,
    )
