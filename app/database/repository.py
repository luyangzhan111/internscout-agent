"""岗位数据库保存与查询操作。"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.database.models import DatasetStateModel, JobModel
from app.schemas.job import JobCreate
from app.services.cleaner import (
    normalize_city,
    normalize_company,
    normalize_skill,
)
from app.services.deduplicator import build_job_identity


JobUpsertOutcome = Literal["created", "updated", "unchanged"]


@dataclass(frozen=True, slots=True)
class JobUpsertResult:
    job: JobModel
    outcome: JobUpsertOutcome


def get_dataset_revision(session: Session) -> int:
    """Read the committed dataset version without creating or changing state."""

    return session.scalar(
        select(DatasetStateModel.revision).where(DatasetStateModel.id == 1)
    ) or 0


def _ensure_dataset_state(session: Session) -> None:
    # This SQLite write also serializes read-modify-write upserts before reading
    # a job, so concurrent writers cannot overwrite a newer snapshot blindly.
    session.execute(
        sqlite_insert(DatasetStateModel)
        .values(id=1, revision=0)
        .on_conflict_do_nothing(index_elements=["id"])
    )


def _advance_dataset_revision(session: Session) -> None:
    session.execute(
        update(DatasetStateModel)
        .where(DatasetStateModel.id == 1)
        .values(revision=DatasetStateModel.revision + 1)
    )


def build_identity_key(job: JobCreate) -> str:
    """将岗位身份转换为可稳定保存的字符串。"""

    identity = build_job_identity(job)

    return json.dumps(
        identity,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def job_model_from_schema(job: JobCreate) -> JobModel:
    """
    将经过验证和清洗的JobCreate转换为数据库ORM对象。

    输入契约：
    岗位应当已经经过process_jobs处理。本函数不会再次执行
    城市、公司和技能标准化。
    """

    return JobModel(
        identity_key=build_identity_key(job),
        title=job.title,
        company=job.company,
        city=job.city,
        salary=job.salary,
        description=job.description,
        skills=list(job.skills),
        source=job.source,
        source_url=job.source_url,
        source_job_id=job.source_job_id,
        status=job.status,
        published_at=job.published_at,
    )


def get_job_by_identity_key(
    session: Session,
    identity_key: str,
) -> JobModel | None:
    """根据岗位身份查询一条数据库记录。"""

    statement = select(JobModel).where(
        JobModel.identity_key == identity_key
    )

    return session.scalar(statement.execution_options(populate_existing=True))


def get_job_by_id(
    session: Session,
    job_id: int,
) -> JobModel | None:
    """根据数据库主键查询岗位。"""

    return session.get(
        JobModel,
        job_id,
    )


def _find_upsert_job(session: Session, job: JobCreate, identity_key: str) -> JobModel | None:
    """Lazily repair old fragment-stripping keys without merging source rows.

    A legacy key may describe a different hash route. Only reuse its row when
    its stored URL identifies the requested job; preserve every other row/ID.
    The caller already holds the SQLite write lock through dataset_state.
    """
    identity = build_job_identity(job)
    if len(identity) < 2 or identity[:2] != ("v2", "source_url"):
        return get_job_by_identity_key(session, identity_key)
    parts = urlsplit(job.source_url)
    legacy_job = job.model_copy(update={
        "source_url": urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, "")),
    })
    keys = dict.fromkeys((identity_key, build_identity_key(legacy_job)))
    found = None
    for key in keys:
        row = get_job_by_identity_key(session, key)
        if row is None:
            continue
        actual_key = build_identity_key(row)
        if row.identity_key != actual_key:
            existing = get_job_by_identity_key(session, actual_key)
            row.identity_key = actual_key if existing is None else json.dumps(
                ["legacy_fragment_conflict", row.id], separators=(",", ":"),
            )
            session.flush()
        if actual_key == identity_key and row.identity_key == identity_key:
            found = row
    return found


def upsert_job(
    session: Session,
    job: JobCreate,
) -> JobUpsertResult:
    """
    保存或更新一条已经清洗的岗位，并返回实际变化类型。

    观察时间表示本次入库，不表示人工或在线验证。未变化的输入只更新
    观察时间；内容或状态变化与数据版本在同一事务中提交。

    事务契约：
    - 本函数会直接提交调用方传入的Session；
    - 发生IntegrityError时会回滚当前Session事务；
    - 调用方应当为岗位持久化提供专用Session；
    - 不应在同一Session中混入无关的未提交数据。
    """

    identity_key = build_identity_key(job)

    for attempt in range(2):
        try:
            _ensure_dataset_state(session)
            database_job = _find_upsert_job(session, job, identity_key)
            observed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            if database_job is None:
                database_job = job_model_from_schema(job)
                session.add(database_job)
                outcome: JobUpsertOutcome = "created"
            else:
                values = job.model_dump()
                changed = any(
                    getattr(database_job, field) != value
                    for field, value in values.items()
                )
                outcome = "updated" if changed else "unchanged"
                if changed:
                    for field, value in values.items():
                        setattr(database_job, field, value)
            database_job.last_seen_at = observed_at
            database_job.last_checked_at = observed_at
            if outcome != "unchanged":
                database_job.updated_at = observed_at
                _advance_dataset_revision(session)
            session.commit()
        except IntegrityError:
            session.rollback()
            # A concurrent insert can win the unique identity constraint. Read
            # its row and retry the complete upsert; unrelated errors propagate.
            if attempt or get_job_by_identity_key(session, identity_key) is None:
                raise
            session.rollback()
            continue
        except Exception:
            session.rollback()
            raise
        session.refresh(database_job)
        return JobUpsertResult(database_job, outcome)
    raise RuntimeError("unreachable upsert retry state")


def save_job(session: Session, job: JobCreate) -> JobModel:
    """Compatibility wrapper returning the created or refreshed job row."""

    return upsert_job(session, job).job


def save_jobs(
    session: Session,
    jobs: list[JobCreate],
) -> list[JobModel]:
    """
    保存多条已经清洗的岗位记录。

    输入列表中的重复岗位只返回一次，并保持第一次出现的顺序。

    当前批量事务采用逐条提交策略：
    - 每条岗位通过save_job独立提交；
    - 后续岗位失败时，之前成功保存的岗位不会被回滚；
    - 当前实现适用于项目中的小批量岗位采集。
    """

    saved_jobs: list[JobModel] = []
    seen_identity_keys: set[str] = set()

    for job in jobs:
        identity_key = build_identity_key(job)

        if identity_key in seen_identity_keys:
            continue

        seen_identity_keys.add(identity_key)

        saved_jobs.append(
            save_job(
                session,
                job,
            )
        )

    return saved_jobs


def list_jobs(
    session: Session,
) -> list[JobModel]:
    """按照数据库主键顺序查询全部岗位。"""

    statement = (
        select(JobModel)
        .order_by(JobModel.id)
    )

    return list(
        session.scalars(statement)
    )


def _build_job_filter_conditions(
    *,
    city: str | None,
    company: str | None,
    skill: str | None,
    source: str | None = None,
    status: str | None = None,
    include_closed: bool = True,
) -> list[ColumnElement[bool]]:
    """根据查询参数构建岗位筛选条件。"""

    conditions: list[ColumnElement[bool]] = []

    if source is not None:
        normalized_source = source.strip().lower()
        if not normalized_source:
            raise ValueError("source cannot be blank")
        conditions.append(JobModel.source == normalized_source)
    if status is not None:
        if status not in {"active", "closed", "unknown"}:
            raise ValueError("status must be active, closed, or unknown")
        conditions.append(JobModel.status == status)
    if not include_closed:
        conditions.append(JobModel.status != "closed")

    if city is not None:
        normalized_city = normalize_city(city)

        if not normalized_city:
            raise ValueError(
                "city不能只包含空白字符"
            )

        conditions.append(
            func.lower(JobModel.city)
            == normalized_city.lower()
        )

    if company is not None:
        normalized_company = normalize_company(
            company
        )

        if not normalized_company:
            raise ValueError(
                "company不能只包含空白字符"
            )

        conditions.append(
            func.lower(JobModel.company)
            == normalized_company.lower()
        )

    if skill is not None:
        normalized_skill = normalize_skill(skill)

        if not normalized_skill:
            raise ValueError(
                "skill不能只包含空白字符"
            )

        skill_values = (
            func.json_each(JobModel.skills)
            .table_valued("value")
            .alias("skill_values")
        )

        conditions.append(
            exists(
                select(1)
                .select_from(skill_values)
                .where(
                    func.lower(
                        skill_values.c.value
                    )
                    == normalized_skill.lower()
                )
            )
        )

    return conditions


def query_jobs(
    session: Session,
    *,
    city: str | None = None,
    company: str | None = None,
    skill: str | None = None,
    page: int = 1,
    page_size: int = 10,
    source: str | None = None,
    status: str | None = None,
    include_closed: bool = True,
) -> tuple[list[JobModel], int]:
    """
    按条件筛选并分页查询岗位。

    返回值：
    - 当前页岗位列表；
    - 符合筛选条件的岗位总数。

    公司、城市和技能均采用精确匹配。
    英文字母比较不区分大小写。
    """

    if page < 1:
        raise ValueError(
            "page必须大于或等于1"
        )

    if page_size < 1 or page_size > 100:
        raise ValueError(
            "page_size必须在1到100之间"
        )

    conditions = _build_job_filter_conditions(
        city=city,
        company=company,
        skill=skill,
        source=source,
        status=status,
        include_closed=include_closed,
    )

    count_statement = (
        select(func.count())
        .select_from(JobModel)
        .where(*conditions)
    )

    total = session.scalar(
        count_statement
    ) or 0

    if total == 0:
        return [], 0

    offset = (
        page - 1
    ) * page_size

    if offset >= total:
        return [], total

    items_statement = (
        select(JobModel)
        .where(*conditions)
        .order_by(JobModel.id)
        .offset(offset)
        .limit(page_size)
    )

    items = list(
        session.scalars(
            items_statement
        )
    )

    return items, total
