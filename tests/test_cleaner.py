"""测试岗位数据清洗功能。"""

import pytest
from pydantic import ValidationError

import app.services.cleaner as cleaner_module
from app.schemas.job import JobCreate
from app.services import (
    clean_job,
    normalize_city,
    normalize_skill,
    normalize_skills,
)


def create_job(**overrides: object) -> JobCreate:
    """创建用于清洗测试的合法岗位。"""

    job_data = {
        "title": "Python后端实习生",
        "company": "星河科技",
        "city": "深圳市",
        "salary": "150-200元/天",
        "description": "负责后端接口开发。",
        "skills": ["python", "FASTAPI", "SQL"],
        "source": "mock",
        "source_url": "https://example.com/jobs/001",
        "published_at": "2026-07-20",
    }
    job_data.update(overrides)

    return JobCreate(**job_data)


def test_normalize_city_removes_city_suffix() -> None:
    """已知城市名称应当转换为项目约定的规范形式。"""

    assert normalize_city("深圳市") == "深圳"
    assert normalize_city(" 广州市 ") == "广州"


def test_normalize_city_keeps_normal_city_name() -> None:
    """未知或无需转换的城市名称不应被错误修改。"""

    assert normalize_city("四日市") == "四日市"
    assert normalize_city("深圳") == "深圳"
    assert normalize_city("新加坡") == "新加坡"


def test_normalize_skill_uses_canonical_name() -> None:
    """技能名称应当转换为项目约定的展示形式。"""

    assert normalize_skill(" python ") == "Python"
    assert normalize_skill("FASTAPI") == "FastAPI"
    assert normalize_skill("PYTEST") == "pytest"
    assert normalize_skill("beautifulsoup4") == "Beautiful Soup"
    assert normalize_skill("beautiful   soup") == "Beautiful Soup"


def test_normalize_skills_removes_blank_and_duplicates() -> None:
    """技能列表应当清除空白值和重复技能。"""

    skills = normalize_skills(
        [
            "python",
            " Python ",
            "",
            "SQL",
            "sql",
            "FastAPI",
        ]
    )

    assert skills == [
        "Python",
        "SQL",
        "FastAPI",
    ]


def test_clean_job_returns_cleaned_copy() -> None:
    """清洗函数应返回新对象，并保留原始岗位不变。"""

    original_job = create_job(
        city="深圳市",
        skills=[
            "python",
            "Python",
            " fastapi ",
            "",
            "SQL",
        ],
    )

    cleaned_job = clean_job(original_job)

    assert cleaned_job.city == "深圳"
    assert cleaned_job.skills == [
        "Python",
        "FastAPI",
        "SQL",
    ]

    assert original_job.city == "深圳市"
    assert original_job.skills == [
        "python",
        "Python",
        "fastapi",
        "",
        "SQL",
    ]


def test_clean_job_revalidates_cleaned_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """清洗结果违反模型约束时应被Pydantic拒绝。"""

    job = create_job()

    monkeypatch.setattr(
        cleaner_module,
        "normalize_city",
        lambda _: "",
    )

    with pytest.raises(ValidationError):
        cleaner_module.clean_job(job)