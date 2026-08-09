"""测试岗位查询API响应模型。"""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.database import JobModel
from app.schemas import (
    JobListResponse,
    JobRead,
)


def create_job_model(
    **overrides: object,
) -> JobModel:
    """创建用于响应模型测试的ORM岗位。"""

    job_data = {
        "id": 1,
        "identity_key": (
            '["星河科技","python后端实习生","深圳"]'
        ),
        "title": "Python后端实习生",
        "company": "星河科技",
        "city": "深圳",
        "salary": "150-200元/天",
        "description": "负责Python后端接口开发。",
        "skills": [
            "Python",
            "FastAPI",
            "SQL",
        ],
        "source": "mock",
        "source_url": "https://example.com/jobs/001",
        "published_at": date(2026, 7, 20),
        "created_at": datetime(2026, 7, 31, 12, 0, 0),
    }
    job_data.update(overrides)

    return JobModel(**job_data)


def test_job_read_can_validate_orm_model() -> None:
    """JobRead应能直接读取SQLAlchemy ORM对象。"""

    database_job = create_job_model()

    response_job = JobRead.model_validate(
        database_job
    )

    assert response_job.id == 1
    assert response_job.title == "Python后端实习生"
    assert response_job.company == "星河科技"
    assert response_job.city == "深圳"
    assert response_job.skills == [
        "Python",
        "FastAPI",
        "SQL",
    ]


def test_job_read_supports_optional_null_fields() -> None:
    """薪资和发布日期为空时仍应生成响应模型。"""

    database_job = create_job_model(
        salary=None,
        published_at=None,
    )

    response_job = JobRead.model_validate(
        database_job
    )

    assert response_job.salary is None
    assert response_job.published_at is None


def test_job_read_does_not_expose_identity_key() -> None:
    """内部岗位身份键不应出现在API响应中。"""

    response_job = JobRead.model_validate(
        create_job_model()
    )

    response_data = response_job.model_dump()

    assert "identity_key" not in response_data


def test_job_list_response_contains_pagination() -> None:
    """岗位列表响应应包含数据和分页信息。"""

    response_job = JobRead.model_validate(
        create_job_model()
    )

    response = JobListResponse(
        items=[response_job],
        total=21,
        page=2,
        page_size=10,
        pages=3,
    )

    assert len(response.items) == 1
    assert response.total == 21
    assert response.page == 2
    assert response.page_size == 10
    assert response.pages == 3


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("page", 0),
        ("page_size", 0),
        ("page_size", 101),
        ("total", -1),
        ("pages", -1),
    ],
)
def test_job_list_response_rejects_invalid_pagination(
    field_name: str,
    invalid_value: int,
) -> None:
    """分页字段超出允许范围时应被Pydantic拒绝。"""

    response_data = {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 10,
        "pages": 0,
    }
    response_data[field_name] = invalid_value

    with pytest.raises(ValidationError):
        JobListResponse(**response_data)
