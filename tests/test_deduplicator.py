"""测试岗位唯一标识和去重功能。"""

from app.schemas.job import JobCreate
from app.services import (
    build_job_identity,
    deduplicate_jobs,
)


def create_job(**overrides: object) -> JobCreate:
    """创建用于去重测试的合法岗位。"""

    job_data = {
        "title": "Python后端实习生",
        "company": "星河科技",
        "city": "深圳市",
        "salary": "150-200元/天",
        "description": "负责后端接口开发。",
        "skills": ["Python", "FastAPI", "SQL"],
        "source": "mock",
        "source_url": "https://example.com/jobs/001",
        "published_at": "2026-07-20",
    }
    job_data.update(overrides)

    return JobCreate(**job_data)


def test_job_identity_normalizes_city_and_case() -> None:
    """城市后缀和英文大小写不应影响岗位身份。"""

    first = create_job(
        title="Python Developer Intern",
        company="Example Tech",
        city="深圳市",
    )
    second = create_job(
        title="python developer intern",
        company="example tech",
        city="深圳",
    )

    assert build_job_identity(first) == build_job_identity(second)


def test_deduplicate_jobs_removes_exact_duplicates() -> None:
    """完全重复的岗位应当只保留一次。"""

    first = create_job()
    duplicate = create_job(
        source_url="https://another.example.com/jobs/001",
    )

    result = deduplicate_jobs([first, duplicate])

    assert result == [first]


def test_deduplicate_jobs_handles_city_variants() -> None:
    """深圳市和深圳应当被视为同一个城市。"""

    first = create_job(city="深圳市")
    duplicate = create_job(
        city="深圳",
        source_url="https://example.com/jobs/duplicate",
    )

    result = deduplicate_jobs([first, duplicate])

    assert result == [first]


def test_different_companies_are_not_duplicates() -> None:
    """岗位名称相同但公司不同，应当保留两条记录。"""

    first = create_job(company="星河科技")
    second = create_job(
        company="云帆软件",
        source_url="https://example.com/jobs/002",
    )

    result = deduplicate_jobs([first, second])

    assert result == [first, second]


def test_different_titles_are_not_duplicates() -> None:
    """公司和城市相同但岗位名称不同，应当保留。"""

    first = create_job(title="Python后端实习生")
    second = create_job(
        title="自动化测试实习生",
        source_url="https://example.com/jobs/002",
    )

    result = deduplicate_jobs([first, second])

    assert result == [first, second]


def test_deduplicate_jobs_preserves_first_seen_order() -> None:
    """去重结果应当保持岗位第一次出现时的顺序。"""

    python_job = create_job()
    test_job = create_job(
        title="自动化测试实习生",
        source_url="https://example.com/jobs/002",
    )
    duplicate_python_job = create_job(
        city="深圳",
        source_url="https://example.com/jobs/duplicate",
    )

    result = deduplicate_jobs(
        [
            python_job,
            test_job,
            duplicate_python_job,
        ]
    )

    assert result == [
        python_job,
        test_job,
    ]

def test_city_names_ending_with_city_character_do_not_collide() -> None:
    """本身以“市”结尾的城市名称不应被错误截断。"""

    first = create_job(city="四日市")
    second = create_job(
        city="四日",
        source_url="https://example.com/jobs/002",
    )

    assert build_job_identity(first) != build_job_identity(second)

    result = deduplicate_jobs([first, second])

    assert result == [first, second]
