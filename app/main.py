"""InternScout Agent 的 FastAPI 应用入口。"""

from fastapi import FastAPI

app = FastAPI(
    title="InternScout Agent",
    description="实习岗位采集与智能匹配助手",
    version="0.1.0",
)


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