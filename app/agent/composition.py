"""Application-level composition for the Agent Runtime."""

from app.agent.model_client import ModelClient
from app.agent.orchestrator import AgentOrchestrator
from app.agent.tools.job_query import JobQueryPort
from app.agent.tools.job_tools import (
    GetJobDetailTool,
    SearchJobsTool,
)
from app.agent.tools.matching_tool import MatchJobsTool
from app.agent.tools.retrieval_tool import RetrieveJobKnowledgeTool
from app.agent.tools.registry import ToolRegistry
from app.matching.matcher import CandidateMatcher
from app.matching.service import JobMatchingService
from app.matching.skill_extractor import JobSkillExtractor
from app.rag.retriever import JobKnowledgeRetriever


def create_agent_orchestrator(
    model_client: ModelClient,
    job_query: JobQueryPort,
    max_steps: int = 5,
    job_retriever: JobKnowledgeRetriever | None = None,
) -> AgentOrchestrator:
    """Create one request-scoped Agent Runtime object graph."""

    matching_service = JobMatchingService(
        job_query=job_query,
        skill_extractor=JobSkillExtractor(),
        matcher=CandidateMatcher(),
    )

    tool_registry = ToolRegistry()
    tool_registry.register(
        SearchJobsTool(job_query=job_query)
    )
    tool_registry.register(
        GetJobDetailTool(job_query=job_query)
    )
    tool_registry.register(
        MatchJobsTool(
            matching_service=matching_service
        )
    )
    if job_retriever is not None:
        tool_registry.register(
            RetrieveJobKnowledgeTool(
                retriever=job_retriever
            )
        )

    return AgentOrchestrator(
        model_client=model_client,
        tool_registry=tool_registry,
        max_steps=max_steps,
    )
