"""测试应用的基础接口。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_read_root() -> None:
    """根路径应返回项目名称和运行状态。"""
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "InternScout Agent",
        "message": "Service is running",
    }


def test_health_check() -> None:
    """健康检查接口应返回ok。"""
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}