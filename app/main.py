"""InternScout Agent FastAPI应用入口。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import (
    agent_router,
    crawl_router,
    health_router,
    jobs_router,
)
from app.api.dependencies import create_retrieval_runtime
from app.database import (
    database_engine,
    init_database,
)


@asynccontextmanager
async def lifespan(
    app: FastAPI,
) -> AsyncIterator[None]:
    """应用启动时初始化当前配置的数据库。"""

    engine = getattr(
        app.state,
        "database_engine",
        database_engine,
    )

    init_database(engine)
    app.state.retrieval_runtime = create_retrieval_runtime()

    yield


app = FastAPI(
    title="InternScout Agent",
    description="实习岗位采集与智能匹配助手",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(crawl_router)
app.include_router(agent_router)


@app.get("/")
def read_root() -> dict[str, str]:
    """返回服务基本信息。"""

    return {
        "name": "InternScout Agent",
        "message": "Service is running",
    }
