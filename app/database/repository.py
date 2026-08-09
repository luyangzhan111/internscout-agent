"""岗位数据库保存与查询操作。"""

import json

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.database.models import JobModel
from app.schemas.job import JobCreate
from app.services.cleaner import (
    normalize_city,
    normalize_company,
    normalize_skill,
)
from app.services.deduplicator import build_job_identity


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

    return session.scalar(statement)


def get_job_by_id(
    session: Session,
    job_id: int,
) -> JobModel | None:
    """根据数据库主键查询岗位。"""

    return session.get(
        JobModel,
        job_id,
    )


def save_job(
    session: Session,
    job: JobCreate,
) -> JobModel:
    """
    保存一条已经清洗的岗位记录。

    岗位已经存在时返回原记录，不重复插入。

    事务契约：
    - 本函数会直接提交调用方传入的Session；
    - 发生IntegrityError时会回滚当前Session事务；
    - 调用方应当为岗位持久化提供专用Session；
    - 不应在同一Session中混入无关的未提交数据。
    """

    identity_key = build_identity_key(job)

    existing_job = get_job_by_identity_key(
        session,
        identity_key,
    )

    if existing_job is not None:
        return existing_job

    database_job = job_model_from_schema(job)
    session.add(database_job)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()

        existing_job = get_job_by_identity_key(
            session,
            identity_key,
        )

        if existing_job is None:
            raise

        return existing_job

    session.refresh(database_job)

    return database_job


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
) -> list[ColumnElement[bool]]:
    """根据查询参数构建岗位筛选条件。"""

    conditions: list[ColumnElement[bool]] = []

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
