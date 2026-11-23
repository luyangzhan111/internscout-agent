"""Crawler policy and mapping for validated OPPO position data."""

from collections.abc import Callable, Sequence
import math
import time

import httpx

from app.crawlers.base import BaseJobCrawler
from app.crawlers.contracts import CrawlBatch, CrawlFailure
from app.crawlers.oppo_source_client import (
    OppoJobSourceClient,
    OppoPositionDetail,
    OppoPositionPage,
    SourceDeadlineExceeded,
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
        max_pages: int = 2,
        max_jobs: int = 20,
        request_interval: float = 0.2,
        time_budget_seconds: float = 45.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Store a caller-owned source client and immutable query policy."""

        if (
            isinstance(page_size, bool)
            or not isinstance(page_size, int)
            or page_size < 1
        ):
            raise ValueError("page_size must be an integer of at least 1")

        for name, value, maximum in (
            ("max_pages", max_pages, 10),
            ("max_jobs", max_jobs, 100),
        ):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f"{name} must be an integer from 1 to {maximum}")
        for name, value, allow_zero in (
            ("request_interval", request_interval, True),
            ("time_budget_seconds", time_budget_seconds, False),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
                or (not allow_zero and value == 0)
            ):
                raise ValueError(f"{name} must be a valid finite duration")

        self._source_client = source_client
        self._recruit_types = tuple(recruit_types)
        self._keyword = keyword
        self._city_codes = tuple(city_codes)
        self._job_types = tuple(job_types)
        self._share_id = share_id
        self._page_size = page_size
        self._max_pages = max_pages
        self._max_jobs = max_jobs
        self._request_interval = float(request_interval)
        self._time_budget_seconds = float(time_budget_seconds)
        self._clock = clock
        self._sleep = sleep

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

    def fetch_batch(self) -> CrawlBatch:
        """Refresh a bounded subset, preserving independently valid details.

        Limits apply to attempted unique jobs, including failures. A partial
        scan never implies that unseen jobs have closed. The legacy
        ``fetch_jobs`` method keeps its strict, all-or-nothing behaviour.
        """

        jobs: list[JobCreate] = []
        failures: list[CrawlFailure] = []
        seen: set[str] = set()
        deadline = self._clock() + self._time_budget_seconds
        previous_request = False
        expected_metadata: tuple[int, int, int] | None = None

        def before_request() -> None:
            nonlocal previous_request
            remaining = deadline - self._clock()
            delay = self._request_interval if previous_request else 0.0
            if remaining <= delay:
                raise SourceDeadlineExceeded("Source refresh deadline exceeded")
            if delay:
                self._sleep(delay)
            if self._clock() >= deadline:
                raise SourceDeadlineExceeded("Source refresh deadline exceeded")
            previous_request = True

        def partial(message: str, item_id: str | None = None) -> CrawlBatch:
            failures.append(CrawlFailure(item_id=item_id, message=message))
            return CrawlBatch(jobs=jobs, failures=failures, complete=False)

        def limited(message: str) -> CrawlBatch:
            return CrawlBatch(
                jobs=jobs, failures=failures, complete=False, warnings=[message]
            )

        for page_num in range(1, self._max_pages + 1):
            try:
                before_request()
                page = self._search_positions(page_num=page_num, deadline=deadline)
            except SourceDeadlineExceeded:
                return limited("本轮刷新已达到时间上限，已保留成功岗位。")
            except (httpx.HTTPError, ValueError):
                return partial(f"第 {page_num} 页岗位列表暂时不可用，已保留成功岗位。")

            metadata = (page.pages, page.total, page.page_size)
            if not self._valid_batch_page(page, page_num):
                return partial(f"第 {page_num} 页岗位数量与分页信息不一致，已停止继续采集。")
            if expected_metadata is not None and metadata != expected_metadata:
                return partial("采集期间岗位总数或分页信息发生变化，请稍后刷新。")
            expected_metadata = metadata

            for position in page.positions:
                position_id = position.position_id
                if position_id in seen:
                    failures.append(CrawlFailure(
                        item_id=position_id,
                        message="来源返回了重复岗位，已跳过重复记录。",
                    ))
                    continue
                seen.add(position_id)
                try:
                    before_request()
                    detail = self._source_client.get_position_detail(
                        position_id, deadline=deadline
                    )
                    if detail.position_id != position_id:
                        raise ValueError("Source returned a different position")
                    jobs.append(self._map_detail(detail))
                except SourceDeadlineExceeded:
                    return limited("本轮刷新已达到时间上限，已保留成功岗位。")
                except httpx.HTTPError:
                    failures.append(CrawlFailure(
                        item_id=position_id,
                        message="岗位详情暂时无法获取，已跳过。",
                    ))
                except ValueError:
                    failures.append(CrawlFailure(
                        item_id=position_id,
                        message="岗位详情格式不符合预期，已跳过。",
                    ))

                if len(seen) >= self._max_jobs:
                    return limited("本轮已达到岗位数量上限，仅更新已获取的岗位。")

            if page_num >= self._max_pages:
                return limited("本轮已达到分页上限，仅更新已获取的岗位。")
            if page_num >= page.pages:
                if len(seen) != page.total:
                    return partial("实际发现的岗位数量与来源总数不一致，请稍后刷新。")
                return CrawlBatch(jobs=jobs, failures=failures, complete=not failures)

        raise AssertionError("A bounded refresh must return a batch")

    def _valid_batch_page(self, page: OppoPositionPage, page_num: int) -> bool:
        """Require exact snapshot counts before treating a page as usable."""

        if page.page_num != page_num or page.page_size != self._page_size:
            return False
        if any(type(value) is not int or value < 0 for value in (page.pages, page.total)):
            return False
        expected_pages = (page.total + page.page_size - 1) // page.page_size
        expected_count = min(page.page_size, max(0, page.total - (page_num - 1) * page.page_size))
        return page.pages == expected_pages and len(page.positions) == expected_count

    def _search_positions(
        self, *, page_num: int, deadline: float | None = None
    ) -> OppoPositionPage:
        """Request one page using the crawler's frozen source policy."""

        deadline_options = {"deadline": deadline} if deadline is not None else {}
        return self._source_client.search_positions(
            page_num=page_num,
            page_size=self._page_size,
            recruit_types=self._recruit_types,
            keyword=self._keyword,
            city_codes=self._city_codes,
            job_types=self._job_types,
            share_id=self._share_id,
            **deadline_options,
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
            source_job_id=detail.position_id,
            status="active",
            source_url=JOB_DETAIL_URL.format(
                position_id=detail.position_id,
                recruit_type=detail.recruit_type,
            ),
            published_at=detail.publish_date,
        )
