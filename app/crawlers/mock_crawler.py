"""从本地模拟招聘页面中解析岗位数据。"""

from pathlib import Path

from bs4 import BeautifulSoup
from bs4.element import Tag
from pydantic import ValidationError

from app.crawlers.base import BaseJobCrawler
from app.schemas.job import JobCreate


DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "sample_jobs.html"
)


class MockJobCrawler(BaseJobCrawler):
    """读取本地HTML文件并解析模拟岗位。"""

    def __init__(self, html_path: str | Path | None = None) -> None:
        """
        初始化模拟爬虫。

        html_path没有传入时，默认读取项目中的sample_jobs.html。
        """
        self.html_path = (
            Path(html_path)
            if html_path is not None
            else DEFAULT_FIXTURE_PATH
        )

    def fetch_jobs(self) -> list[JobCreate]:
        """读取HTML文件，并返回解析后的岗位列表。"""

        if not self.html_path.is_file():
            raise FileNotFoundError(
                f"模拟招聘文件不存在：{self.html_path}"
            )

        html = self.html_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        job_cards = soup.select("article.job-card")

        if not job_cards:
            raise ValueError("模拟招聘页面中没有找到岗位卡片")

        jobs = [
            self._parse_job_card(card, card_number)
            for card_number, card in enumerate(job_cards, start=1)
        ]

        return jobs

    def _parse_job_card(
        self,
        card: Tag,
        card_number: int,
    ) -> JobCreate:
        """将单个岗位卡片解析为JobCreate对象。"""

        title = self._get_required_text(
            card,
            ".job-title",
            card_number,
        )
        company = self._get_required_text(
            card,
            ".company",
            card_number,
        )
        city = self._get_required_text(
            card,
            ".city",
            card_number,
        )
        description = self._get_required_text(
            card,
            ".description",
            card_number,
        )

        salary = self._get_optional_text(card, ".salary")

        skills: list[str] = []

        for item in card.select(".skills li"):
            skill = item.get_text(" ", strip=True)

            if skill:
                skills.append(skill)

        published_node = card.select_one(".published-at")
        published_at: str | None = None

        if published_node is not None:
            raw_datetime = published_node.get("datetime")

            datetime_value = (
                raw_datetime.strip()
                if isinstance(raw_datetime, str)
                else ""
            )
            text_value = published_node.get_text(" ", strip=True)

            published_at = datetime_value or text_value or None

        source_url = self._get_required_attribute(
            card,
            ".source-url",
            "href",
            card_number,
        )

        try:
             return JobCreate(
                title=title,
                company=company,
                city=city,
                salary=salary,
                description=description,
                skills=skills,
                source="mock",
                source_url=source_url,
                published_at=published_at,
            )
        except ValidationError as exc:
            raise ValueError(
                f"第{card_number}条岗位数据校验失败，"
                f"文件：{self.html_path}"
            ) from exc

    @staticmethod
    def _get_required_text(
        card: Tag,
        selector: str,
        card_number: int,
    ) -> str:
        """读取必填文本字段，缺失或为空时抛出明确异常。"""

        node = card.select_one(selector)

        if node is None:
            raise ValueError(
                f"第{card_number}条岗位缺少必填字段：{selector}"
            )

        value = node.get_text(" ", strip=True)

        if not value:
            raise ValueError(
                f"第{card_number}条岗位的必填字段为空：{selector}"
            )

        return value

    @staticmethod
    def _get_optional_text(
        card: Tag,
        selector: str,
    ) -> str | None:
        """读取可选文本字段，不存在或为空时返回None。"""

        node = card.select_one(selector)

        if node is None:
            return None

        value = node.get_text(" ", strip=True)

        return value or None

    @staticmethod
    def _get_required_attribute(
        card: Tag,
        selector: str,
        attribute: str,
        card_number: int,
    ) -> str:
        """读取HTML元素的必填属性。"""

        node = card.select_one(selector)

        if node is None:
            raise ValueError(
                f"第{card_number}条岗位缺少元素：{selector}"
            )

        value = node.get(attribute)

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"第{card_number}条岗位缺少属性："
                f"{selector}[{attribute}]"
            )

        return value.strip()