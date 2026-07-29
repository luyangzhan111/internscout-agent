"""测试岗位清洗和去重处理管道。"""

from app.schemas.job import JobCreate
from app.services import process_jobs
from app.crawlers import MockJobCrawler

def create_job(**overrides: object) -> JobCreate:
    """创建用于处理管道测试的合法岗位。"""

    job_data = {
        "title": "Python Developer Intern",
        "company": "Example Tech",
        "city": "深圳市",
        "salary": "150-200元/天",
        "description": "负责Python后端接口开发。",
        "skills": ["python", "SQL"],
        "source": "mock",
        "source_url": "https://example.com/jobs/001",
        "published_at": "2026-07-20",
    }
    job_data.update(overrides)

    return JobCreate(**job_data)


def test_process_jobs_cleans_and_deduplicates() -> None:
    """处理管道应先清洗岗位，再删除重复数据。"""

    first = create_job(
        skills=[
            "python",
            " Python ",
            "",
            "sql",
        ],
    )
    duplicate = create_job(
        title="python developer intern",
        company="example tech",
        city="深圳",
        skills=["FastAPI"],
        source_url="https://example.com/jobs/duplicate",
    )

    result = process_jobs([first, duplicate])

    assert len(result) == 1
    assert result[0].city == "深圳"
    assert result[0].skills == [
        "Python",
        "SQL",
    ]
    assert result[0].source_url == (
        "https://example.com/jobs/001"
    )


def test_process_jobs_keeps_different_jobs() -> None:
    """不同岗位经过处理后仍应全部保留。"""

    python_job = create_job()
    test_job = create_job(
        title="自动化测试实习生",
        company="云帆软件",
        city="广州市",
        skills=["python", "pytest", "SQL"],
        source_url="https://example.com/jobs/002",
    )

    result = process_jobs([
        python_job,
        test_job,
    ])

    assert len(result) == 2
    assert result[0].city == "深圳"
    assert result[1].city == "广州"
    assert result[1].skills == [
        "Python",
        "pytest",
        "SQL",
    ]


def test_process_jobs_does_not_modify_original_jobs() -> None:
    """处理管道不应直接修改输入的岗位对象。"""

    original = create_job(
        city="深圳市",
        skills=[
            "python",
            "Python",
            "",
        ],
    )

    result = process_jobs([original])

    assert result[0].city == "深圳"
    assert result[0].skills == ["Python"]

    assert original.city == "深圳市"
    assert original.skills == [
        "python",
        "Python",
        "",
    ]


def test_process_jobs_accepts_empty_list() -> None:
    """空岗位列表应当得到空结果，而不是产生异常。"""

    assert process_jobs([]) == []

def test_process_mock_crawler_jobs_integration() -> None:
    """模拟爬虫输出应能直接进入清洗和去重管道。"""

    raw_jobs = MockJobCrawler().fetch_jobs()

    result = process_jobs(raw_jobs)

    assert len(result) == 6
    assert [job.city for job in result] == [
        "深圳",
        "广州",
        "上海",
        "深圳",
        "北京",
        "东莞",
    ]
    assert result[1].skills == [
        "Python",
        "pytest",
        "HTTP",
        "SQL",
    ]
    assert result[2].skills == [
        "Python",
        "Requests",
        "Beautiful Soup",
        "SQL",
    ]
