"""Crawler policy and mapping for validated OPPO position data."""

from collections.abc import Sequence

from app.crawlers.base import BaseJobCrawler
from app.crawlers.oppo_source_client import (
    OppoJobSourceClient,
    OppoPositionDetail,
    OppoPositionPage,
)
from app.schemas.job import JobCreate


DEFAULT_RECRUIT_TYPE = "OFFEN-RECRUITMENT"
DEFAULT_PAGE_SIZE = 20
JOB_DETAIL_URL = (
    "https://career.oppo.com/official/oppo/recruitment/post/"
    "{position_id}?recruitType={recruit_type}"
)


class OppoJobCrawler(BaseJobCrawler):
    """Discover OPPO internships and map their details to ``JobCreate``."""

    def __init__(
        self,
        source_client: OppoJobSourceClient,
        *,
        recruit_types: Sequence[str] = (DEFAULT_RECRUIT_TYPE,),
        keyword: str = "",
        city_codes: Sequence[str] = (),
        job_types: Sequence[str] = (),
        share_id: str = "",
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> None:
        """Store a caller-owned source client and immutable query policy."""

        if (
            isinstance(page_size, bool)
            or not isinstance(page_size, int)
            or page_size < 1
        ):
            raise ValueError("page_size must be an integer of at least 1")

        self._source_client = source_client
        self._recruit_types = tuple(recruit_types)
        self._keyword = keyword
        self._city_codes = tuple(city_codes)
        self._job_types = tuple(job_types)
        self._share_id = share_id
        self._page_size = page_size

    def fetch_jobs(self) -> list[JobCreate]:
        """Fetch all discovery pages, then fetch and map details in order."""

        first_page = self._search_positions(page_num=1)
        position_ids = [
            position.position_id for position in first_page.positions
        ]

        for page_num in range(2, first_page.pages + 1):
            page = self._search_positions(page_num=page_num)
            position_ids.extend(
                position.position_id for position in page.positions
            )

        jobs: list[JobCreate] = []
        for position_id in position_ids:
            detail = self._source_client.get_position_detail(position_id)
            jobs.append(self._map_detail(detail))

        return jobs

    def _search_positions(self, *, page_num: int) -> OppoPositionPage:
        """Request one page using the crawler's frozen source policy."""

        return self._source_client.search_positions(
            page_num=page_num,
            page_size=self._page_size,
            recruit_types=self._recruit_types,
            keyword=self._keyword,
            city_codes=self._city_codes,
            job_types=self._job_types,
            share_id=self._share_id,
        )

    @staticmethod
    def _map_detail(detail: OppoPositionDetail) -> JobCreate:
        """Map one source-validated OPPO detail into the existing schema."""

        return JobCreate(
            title=detail.publish_name,
            company="OPPO",
            city=detail.work_city_name,
            salary=None,
            description=(
                f"岗位职责：\n{detail.job_duty}\n\n"
                f"任职要求：\n{detail.work_require}"
            ),
            skills=[],
            source="oppo",
            source_url=JOB_DETAIL_URL.format(
                position_id=detail.position_id,
                recruit_type=detail.recruit_type,
            ),
            published_at=detail.publish_date,
        )
