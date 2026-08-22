"""测试SQLite连接、会话工厂和数据库初始化。"""

import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.database import (
    DEFAULT_DATABASE_URL,
    create_database_engine,
    create_session_factory,
    init_database,
)
from app.database.session import (
    DATABASE_URL_ENV,
    get_database_url,
)


def create_test_database_url(
    database_path: Path,
) -> str:
    """根据临时文件路径生成SQLite数据库地址。"""

    return f"sqlite:///{database_path.as_posix()}"


def test_default_database_url_targets_project_file() -> None:
    """默认数据库地址应指向项目目录中的SQLite文件。"""

    assert DEFAULT_DATABASE_URL == "sqlite:///./internscout.db"


def test_get_database_url_uses_local_default_when_environment_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """缺少环境变量时应保持既有本地SQLite地址。"""

    monkeypatch.delenv(DATABASE_URL_ENV, raising=False)

    assert get_database_url() == DEFAULT_DATABASE_URL


def test_get_database_url_uses_environment_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配置环境变量后应返回去除首尾空白的数据库地址。"""

    configured_url = " sqlite:////data/internscout.db "
    monkeypatch.setenv(DATABASE_URL_ENV, configured_url)

    assert get_database_url() == "sqlite:////data/internscout.db"


def test_environment_override_configures_shared_engine_and_session(
    tmp_path: Path,
) -> None:
    """模块级Engine、SessionLocal和get_session应共享环境配置。"""

    database_url = create_test_database_url(tmp_path / "configured.db")
    project_root = Path(__file__).resolve().parents[1]
    check_script = """
from app.database.session import SessionLocal, database_engine, get_session

assert database_engine.url.get_backend_name() == "sqlite"
assert str(database_engine.url.database).replace("\\\\", "/").endswith("/configured.db")
assert SessionLocal.kw["bind"] is database_engine

session_generator = get_session()
session = next(session_generator)
try:
    assert session.bind is database_engine
finally:
    session_generator.close()
"""

    environment = os.environ.copy()
    environment[DATABASE_URL_ENV] = database_url
    result = subprocess.run(
        [sys.executable, "-c", check_script],
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_create_database_engine_uses_requested_url(
    tmp_path: Path,
) -> None:
    """Engine应使用传入的SQLite数据库地址。"""

    database_path = tmp_path / "engine-test.db"
    database_url = create_test_database_url(database_path)

    engine = create_database_engine(database_url)

    assert engine.url.get_backend_name() == "sqlite"
    assert engine.url.database is not None
    assert engine.url.database.replace("\\", "/").endswith(
        "/engine-test.db"
    )

    engine.dispose()


def test_init_database_creates_jobs_table(
    tmp_path: Path,
) -> None:
    """初始化数据库后应创建jobs表。"""

    database_path = tmp_path / "init-test.db"
    engine = create_database_engine(
        create_test_database_url(database_path)
    )

    assert database_path.exists() is False

    init_database(engine)

    table_names = inspect(engine).get_table_names()

    assert database_path.exists() is True
    assert "jobs" in table_names

    engine.dispose()


def test_init_database_can_run_more_than_once(
    tmp_path: Path,
) -> None:
    """数据库初始化函数应当可以安全地重复执行。"""

    database_path = tmp_path / "repeat-test.db"
    engine = create_database_engine(
        create_test_database_url(database_path)
    )

    init_database(engine)
    init_database(engine)

    assert inspect(engine).get_table_names() == ["jobs"]

    engine.dispose()


def test_session_factory_creates_configured_session(
    tmp_path: Path,
) -> None:
    """会话工厂应创建绑定到指定Engine的Session。"""

    database_path = tmp_path / "session-test.db"
    engine = create_database_engine(
        create_test_database_url(database_path)
    )
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        assert isinstance(session, Session)
        assert session.bind is engine
        assert session.autoflush is False
        assert session.expire_on_commit is False

    engine.dispose()
