"""测试SQLite连接、会话工厂和数据库初始化。"""

from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.database import (
    DEFAULT_DATABASE_URL,
    create_database_engine,
    create_session_factory,
    init_database,
)


def create_test_database_url(
    database_path: Path,
) -> str:
    """根据临时文件路径生成SQLite数据库地址。"""

    return f"sqlite:///{database_path.as_posix()}"


def test_default_database_url_targets_project_file() -> None:
    """默认数据库地址应指向项目目录中的SQLite文件。"""

    assert DEFAULT_DATABASE_URL == "sqlite:///./internscout.db"


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
