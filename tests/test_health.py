"""测试服务根接口和数据库健康检查接口。"""

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import (
    create_database_engine,
    create_session_factory,
    database_engine,
    get_session,
)
from app.main import app


@pytest.fixture
def health_api_client(
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    """创建使用临时SQLite数据库的健康检查客户端。"""

    database_path = (
        tmp_path
        / "health-api-test.db"
    )

    database_url = (
        f"sqlite:///{database_path.as_posix()}"
    )

    engine = create_database_engine(
        database_url
    )

    session_factory = (
        create_session_factory(
            engine
        )
    )

    def override_get_session(
    ) -> Generator[
        Session,
        None,
        None,
    ]:
        """为健康检查提供临时数据库会话。"""

        with session_factory() as session:
            yield session

    app.state.database_engine = engine

    app.dependency_overrides[
        get_session
    ] = override_get_session

    try:
        assert database_path.exists() is False

        with TestClient(app) as client:
            assert database_path.exists() is True

            yield client

    finally:
        app.dependency_overrides.pop(
            get_session,
            None,
        )

        app.state.database_engine = (
            database_engine
        )

        engine.dispose()


def test_read_root(
    health_api_client: TestClient,
) -> None:
    """根接口应返回服务基本信息。"""

    response = health_api_client.get("/")

    assert response.status_code == 200

    assert response.json() == {
        "name": "InternScout Agent",
        "message": "Service is running",
    }


def test_health_check_returns_database_status(
    health_api_client: TestClient,
) -> None:
    """数据库可用时健康检查应返回200。"""

    response = health_api_client.get(
        "/api/health"
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "ok",
        "database": "ok",
    }


def test_health_check_returns_503_when_database_fails(
    health_api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """数据库查询失败时健康检查应返回503。"""

    def fail_execute(
        self: Session,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        raise SQLAlchemyError(
            "simulated database failure"
        )

    monkeypatch.setattr(
        Session,
        "execute",
        fail_execute,
    )

    response = health_api_client.get(
        "/api/health"
    )

    assert response.status_code == 503

    assert response.json() == {
        "detail": "数据库不可用",
    }
