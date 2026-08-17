"""FastAPI路由模块。"""

from app.api.routes.agent import router as agent_router
from app.api.routes.crawl import router as crawl_router
from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router

__all__ = [
    "agent_router",
    "crawl_router",
    "health_router",
    "jobs_router",
]
