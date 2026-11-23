"""SQLAlchemy数据库模型。"""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有SQLAlchemy ORM模型的基类。"""


class JobModel(Base):
    """数据库中的岗位记录。"""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    identity_key: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        unique=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    company: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    city: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    salary: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    skills: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source_job_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown", server_default="unknown"
    )

    published_at: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    # UTC timestamps. Observation/check means ingestion, not manual verification.
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        """返回便于调试的岗位描述。"""

        return (
            "JobModel("
            f"id={self.id!r}, "
            f"title={self.title!r}, "
            f"company={self.company!r}, "
            f"city={self.city!r}"
            ")"
        )


class DatasetStateModel(Base):
    """Single-row version shared by writers and process-local search indexes."""

    __tablename__ = "dataset_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
