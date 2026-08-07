"""InternScout Agent 的 FastAPI 应用入口。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import jobs_router
from app.database import (
    database_engine,
    init_database,
)


@asynccontextmanager
async def lifespan(
    application: FastAPI,
) -> AsyncIterator[None]:
    """应用启动时初始化当前配置的数据库表。"""

    engine = getattr(
        application.state,
        "database_engine",
        database_engine,
    )

    init_database(engine)

    yield


app = FastAPI(
    title="InternScout Agent",
    description="实习岗位采集与智能匹配助手",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(jobs_router)


@app.get("/")
def read_root() -> dict[str, str]:
    """返回项目基础信息。"""

    return {
        "name": "InternScout Agent",
        "message": "Service is running",
    }


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """供测试和部署环境检查服务是否正常。"""

    return {"status": "ok"}
