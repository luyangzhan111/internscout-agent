"""SQLite数据库连接与会话管理。"""

from collections.abc import Generator
import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Base


DEFAULT_DATABASE_URL = "sqlite:///./internscout.db"
DATABASE_URL_ENV = "INTERNSCOUT_DATABASE_URL"


def get_database_url() -> str:
    """Return the configured database URL or the local SQLite default."""

    configured_url = os.getenv(DATABASE_URL_ENV)
    if configured_url is None or not configured_url.strip():
        return DEFAULT_DATABASE_URL

    return configured_url.strip()


def create_database_engine(
    database_url: str = DEFAULT_DATABASE_URL,
) -> Engine:
    """根据数据库地址创建SQLAlchemy Engine。"""

    connect_args: dict[str, object] = {}

    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        database_url,
        connect_args=connect_args,
    )


def create_session_factory(
    engine: Engine,
) -> sessionmaker[Session]:
    """创建绑定到指定Engine的数据库会话工厂。"""

    return sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )


database_engine = create_database_engine(get_database_url())
SessionLocal = create_session_factory(database_engine)


def init_database(
    engine: Engine = database_engine,
) -> None:
    """创建当前SQLAlchemy元数据中尚不存在的数据库表。"""

    Base.metadata.create_all(bind=engine)


def get_session() -> Generator[Session, None, None]:
    """提供数据库会话，并在使用结束后自动关闭。"""

    with SessionLocal() as session:
        yield session
