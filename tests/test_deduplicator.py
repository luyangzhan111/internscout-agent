"""测试岗位唯一标识和去重功能。"""

import pytest

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


def test_source_ids_separate_same_name_jobs_and_survive_title_changes() -> None:
    first = create_job(source=" OPPO ", source_job_id="A")
    renamed = create_job(source="oppo", source_job_id="A", title="New title")
    other_team = create_job(source="oppo", source_job_id="B")
    other_case = create_job(source="oppo", source_job_id="a")
    other_source = create_job(source="another", source_job_id="A")
    assert build_job_identity(first) == build_job_identity(renamed)
    assert len(deduplicate_jobs([first, renamed, other_team, other_case, other_source])) == 4


def test_mock_legacy_tuple_cannot_collide_with_source_identity_namespace() -> None:
    legacy = create_job(company="source_id", title="oppo", city="a")
    real = create_job(source="oppo", source_job_id="a")
    assert build_job_identity(legacy) != build_job_identity(real)


def test_manual_ids_are_metadata_and_never_merge_different_source_sites() -> None:
    first = create_job(source="manual", source_job_id="123", source_url="https://one.example/jobs/123")
    other_site = create_job(source="manual", source_job_id="123", source_url="https://two.example/jobs/123")
    without_id = create_job(source="manual", source_url=first.source_url)
    assert build_job_identity(first) != build_job_identity(other_site)
    assert build_job_identity(first) == build_job_identity(without_id)


def test_real_sources_use_url_identity_without_cross_source_merging() -> None:
    first = create_job(source="manual", source_url="HTTPS://Example.COM:443/jobs/A?q=1#top")
    same = create_job(source="manual", source_url="https://example.com/jobs/A?q=1#top")
    other_path = create_job(source="manual", source_url="https://example.com/jobs/a?q=1")
    other_query = create_job(source="manual", source_url="https://example.com/jobs/A?q=2")
    other_source = create_job(source="oppo", source_url=first.source_url)
    assert build_job_identity(first) == build_job_identity(same)
    assert len(deduplicate_jobs([first, same, other_path, other_query, other_source])) == 4


def test_manual_hash_routes_identify_distinct_jobs() -> None:
    first = create_job(source="manual", source_job_id="11", source_url="https://careers.company.test/#/jobs/11")
    other = create_job(source="manual", source_job_id="22", source_url="https://careers.company.test/#/jobs/22")
    assert build_job_identity(first) != build_job_identity(other)
    assert deduplicate_jobs([first, other, first]) == [first, other]


@pytest.mark.parametrize("url", ["not-a-url", "file:///jobs/1", "https://user:secret@example.com/1"])
def test_real_source_without_id_requires_http_identity(url: str) -> None:
    with pytest.raises(ValueError):
        build_job_identity(create_job(source="manual", source_url=url))
