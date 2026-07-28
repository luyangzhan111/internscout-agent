"""测试本地模拟岗位爬虫。"""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.crawlers import MockJobCrawler
from app.schemas.job import JobCreate


def write_single_job_html(
    tmp_path: Path,
    *,
    salary_html: str = (
        '<span class="salary">100元/天</span>'
    ),
    published_html: str = (
        '<time class="published-at" datetime="2026-07-20">'
        "2026-07-20"
        "</time>"
    ),
) -> Path:
    """写入一条结构完整的临时岗位页面。"""

    html_file = tmp_path / "single-job.html"
    html_file.write_text(
        f"""
        <html>
        <body>
            <article class="job-card">
                <h2 class="job-title">测试实习生</h2>
                <p class="company">测试公司</p>
                <span class="city">深圳</span>

                {salary_html}
                {published_html}

                <p class="description">
                    负责测试项目开发。
                </p>

                <ul class="skills">
                    <li>Python</li>
                    <li>SQL</li>
                </ul>

                <a
                    class="source-url"
                    href="https://example.com/jobs/test"
                >
                    查看岗位
                </a>
            </article>
        </body>
        </html>
        """,
        encoding="utf-8",
    )

    return html_file

def test_blank_datetime_falls_back_to_visible_text(
    tmp_path: Path,
) -> None:
    """空白datetime属性应当回退到time标签正文。"""

    html_file = write_single_job_html(
        tmp_path,
        published_html=(
            '<time class="published-at" datetime="   ">'
            "2026-07-20"
            "</time>"
        ),
    )

    job = MockJobCrawler(html_file).fetch_jobs()[0]

    assert job.published_at == date(2026, 7, 20)

def test_invalid_date_error_includes_job_context(
    tmp_path: Path,
) -> None:
    """非法日期错误应当指出岗位序号并保留原异常。"""

    html_file = write_single_job_html(
        tmp_path,
        published_html=(
            '<time class="published-at" datetime="invalid-date">'
            "invalid-date"
            "</time>"
        ),
    )

    with pytest.raises(
        ValueError,
        match="第1条岗位数据校验失败",
    ) as exc_info:
        MockJobCrawler(html_file).fetch_jobs()

    assert isinstance(
        exc_info.value.__cause__,
        ValidationError,
    )

def test_blank_salary_is_parsed_as_none(
    tmp_path: Path,
) -> None:
    """薪资元素存在但内容为空白时应返回None。"""

    html_file = write_single_job_html(
        tmp_path,
        salary_html='<span class="salary">   </span>',
    )

    job = MockJobCrawler(html_file).fetch_jobs()[0]

    assert job.salary is None

def test_default_fixture_path_is_independent_of_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """从其他工作目录运行时仍应找到默认模拟页面。"""

    monkeypatch.chdir(tmp_path)

    jobs = MockJobCrawler().fetch_jobs()

    assert len(jobs) == 6

def test_fetch_jobs_returns_six_job_models() -> None:
    """模拟页面应当被解析为6个JobCreate对象。"""

    jobs = MockJobCrawler().fetch_jobs()

    assert len(jobs) == 6
    assert all(isinstance(job, JobCreate) for job in jobs)


def test_first_job_fields_are_parsed_correctly() -> None:
    """第一条岗位的主要字段应当正确解析。"""

    job = MockJobCrawler().fetch_jobs()[0]

    assert job.title == "Python后端实习生"
    assert job.company == "星河科技"
    assert job.city == "深圳市"
    assert job.salary == "150-200元/天"
    assert job.source == "mock"
    assert job.source_url == "https://example.com/jobs/001"


def test_job_skills_are_parsed_as_list() -> None:
    """HTML中的多个技能标签应当组成技能列表。"""

    job = MockJobCrawler().fetch_jobs()[0]

    assert job.skills == [
        "Python",
        "FastAPI",
        "SQL",
        "Git",
    ]


def test_published_at_is_converted_to_date() -> None:
    """HTML日期字符串应当被Pydantic转换为date对象。"""

    job = MockJobCrawler().fetch_jobs()[0]

    assert job.published_at == date(2026, 7, 20)


def test_missing_salary_is_parsed_as_none() -> None:
    """缺少薪资元素的岗位仍应当成功解析。"""

    job = MockJobCrawler().fetch_jobs()[-1]

    assert job.title == "软件测试实习生"
    assert job.salary is None


def test_missing_html_file_raises_file_not_found_error(
    tmp_path,
) -> None:
    """HTML文件不存在时应当抛出明确异常。"""

    missing_file = tmp_path / "not-found.html"
    crawler = MockJobCrawler(missing_file)

    with pytest.raises(
        FileNotFoundError,
        match="模拟招聘文件不存在",
    ):
        crawler.fetch_jobs()


def test_page_without_job_cards_raises_value_error(
    tmp_path,
) -> None:
    """页面中没有岗位卡片时应当抛出异常。"""

    html_file = tmp_path / "empty.html"
    html_file.write_text(
        "<html><body><p>没有岗位</p></body></html>",
        encoding="utf-8",
    )

    crawler = MockJobCrawler(html_file)

    with pytest.raises(
        ValueError,
        match="没有找到岗位卡片",
    ):
        crawler.fetch_jobs()


def test_missing_required_field_raises_clear_error(
    tmp_path,
) -> None:
    """岗位缺少必填字段时，错误信息应指出具体字段。"""

    html_file = tmp_path / "missing-title.html"
    html_file.write_text(
        """
        <html>
        <body>
            <article class="job-card">
                <p class="company">测试公司</p>
                <span class="city">深圳</span>
                <p class="description">测试岗位描述</p>

                <ul class="skills">
                    <li>Python</li>
                </ul>

                <a
                    class="source-url"
                    href="https://example.com/jobs/test"
                >
                    查看岗位
                </a>
            </article>
        </body>
        </html>
        """,
        encoding="utf-8",
    )

    crawler = MockJobCrawler(html_file)

    with pytest.raises(
        ValueError,
        match=r"缺少必填字段：\.job-title",
    ):
        crawler.fetch_jobs()