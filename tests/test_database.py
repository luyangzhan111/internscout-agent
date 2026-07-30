"""测试SQLAlchemy岗位数据库模型。"""

from sqlalchemy import JSON

from app.database import Base, JobModel


def test_job_model_is_registered_in_metadata() -> None:
    """岗位表应当注册到SQLAlchemy元数据中。"""

    assert "jobs" in Base.metadata.tables
    assert Base.metadata.tables["jobs"] is JobModel.__table__


def test_job_model_uses_jobs_table() -> None:
    """岗位ORM模型应当对应jobs表。"""

    assert JobModel.__tablename__ == "jobs"


def test_job_table_contains_expected_columns() -> None:
    """岗位表应当包含项目持久化所需的全部字段。"""

    column_names = set(JobModel.__table__.columns.keys())

    assert column_names == {
        "id",
        "identity_key",
        "title",
        "company",
        "city",
        "salary",
        "description",
        "skills",
        "source",
        "source_url",
        "published_at",
        "created_at",
    }


def test_job_table_nullable_contract() -> None:
    """必填字段与可选字段的数据库约束应当正确。"""

    columns = JobModel.__table__.columns

    assert columns["title"].nullable is False
    assert columns["company"].nullable is False
    assert columns["city"].nullable is False
    assert columns["description"].nullable is False
    assert columns["skills"].nullable is False
    assert columns["source"].nullable is False
    assert columns["source_url"].nullable is False

    assert columns["salary"].nullable is True
    assert columns["published_at"].nullable is True


def test_identity_key_has_unique_constraint() -> None:
    """岗位身份字段必须具有数据库唯一约束。"""

    identity_column = JobModel.__table__.columns["identity_key"]

    assert identity_column.nullable is False
    assert identity_column.unique is True


def test_skills_column_uses_json_type() -> None:
    """技能列表应当使用JSON类型保存。"""

    skills_column = JobModel.__table__.columns["skills"]

    assert isinstance(skills_column.type, JSON)
