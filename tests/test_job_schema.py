"""测试岗位数据模型。"""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.job import JobCreate


def create_valid_job(**overrides: object) -> JobCreate:
    """创建一条默认合法岗位，允许测试覆盖指定字段。"""

    job_data = {
        "title": "Python后端实习生",
        "company": "星河科技",
        "city": "深圳市",
        "salary": "150-200元/天",
        "description": "负责FastAPI接口开发，要求熟悉Python和SQL。",
        "skills": ["Python", "FastAPI", "SQL"],
        "source": "mock",
        "source_url": "https://example.com/jobs/001",
        "published_at": "2026-07-20",
    }
    job_data.update(overrides)

    return JobCreate(**job_data)


def test_create_valid_job() -> None:
    """合法岗位数据应当成功创建。"""

    job = create_valid_job()

    assert job.title == "Python后端实习生"
    assert job.company == "星河科技"
    assert job.skills == ["Python", "FastAPI", "SQL"]
    assert job.published_at == date(2026, 7, 20)


def test_job_model_strips_whitespace() -> None:
    """字符串字段首尾的空格应当被自动去除。"""

    job = create_valid_job(
        title="  Python后端实习生  ",
        company="  星河科技  ",
    )

    assert job.title == "Python后端实习生"
    assert job.company == "星河科技"


def test_job_model_allows_missing_salary() -> None:
    """没有公开薪资的岗位仍应当可以创建。"""

    job = create_valid_job(salary=None)

    assert job.salary is None


def test_job_model_rejects_blank_title() -> None:
    """空岗位名称必须被拒绝。"""

    with pytest.raises(ValidationError):
        create_valid_job(title="   ")