"""数据库模型、连接和岗位持久化模块。"""

from app.database.models import Base, JobModel
from app.database.repository import (
    build_identity_key,
    get_job_by_identity_key,
    job_model_from_schema,
    list_jobs,
    save_job,
    save_jobs,
)
from app.database.session import (
    DEFAULT_DATABASE_URL,
    SessionLocal,
    create_database_engine,
    create_session_factory,
    database_engine,
    get_session,
    init_database,
)

__all__ = [
    "Base",
    "DEFAULT_DATABASE_URL",
    "JobModel",
    "SessionLocal",
    "build_identity_key",
    "create_database_engine",
    "create_session_factory",
    "database_engine",
    "get_job_by_identity_key",
    "get_session",
    "init_database",
    "job_model_from_schema",
    "list_jobs",
    "save_job",
    "save_jobs",
]
