"""FastAPI路由模块。"""

from app.api.routes.agent import router as agent_router
from app.api.routes.crawl import router as crawl_router
from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.imports import router as imports_router
from app.api.routes.eligibility import router as eligibility_router
from app.api.routes.recommendations import router as recommendations_router

__all__ = [
    "agent_router",
    "crawl_router",
    "health_router",
    "jobs_router",
    "imports_router",
    "eligibility_router",
    "recommendations_router",
]
