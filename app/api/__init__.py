"""项目FastAPI接口模块。"""

from app.api.routes import (
    agent_router,
    crawl_router,
    health_router,
    jobs_router,
)

__all__ = [
    "agent_router",
    "crawl_router",
    "health_router",
    "jobs_router",
]
