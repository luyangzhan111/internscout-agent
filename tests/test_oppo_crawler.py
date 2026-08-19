"""Network-free tests for the OPPO crawler boundary."""

from collections.abc import Sequence
from datetime import date
from typing import Any

import pytest

from app.crawlers.base import BaseJobCrawler
from app.crawlers.oppo_crawler import OppoJobCrawler
from app.crawlers.oppo_source_client import (
    OppoPositionDetail,
    OppoPositionPage,
    OppoPositionSummary,
)
from app.schemas.job import JobCreate


def position_page(
    page_num: int,
    pages: int,
    total: int,
    *position_ids: str,
    page_size: int = 20,
) -> OppoPositionPage:
    """Build one source-validated discovery page for a fake client."""

    return OppoPositionPage(
        page_num=page_num,
        page_size=page_size,
        pages=pages,
        total=total,
        positions=tuple(
            OppoPositionSummary(position_id=value)
            for value in position_ids
        ),
    )


def position_detail(
    position_id: str,
    *,
    publish_name: str = "AI产品实习生",
    publish_date: date = date(2026, 6, 1),
    recruit_type: str = "OFFEN-RECRUITMENT",
    work_city_name: str = "东莞市",
    job_duty: str = "负责产品调研与需求分析。",
    work_require: str = "具备良好的沟通和分析能力。",
) -> OppoPositionDetail:
    """Build one source-validated detail for a fake client."""

    return OppoPositionDetail(
        position_id=position_id,
        publish_name=publish_name,
        publish_date=publish_date,
        recruit_type=recruit_type,
        work_city_name=work_city_name,
        job_duty=job_duty,
        work_require=work_require,
    )


class FakeOppoJobSourceClient:
    """Record crawler orchestration while returning typed source values."""

    def __init__(
        self,
        pages: dict[int, OppoPositionPage | Exception],
        details: dict[str, OppoPositionDetail | Exception] | None = None,
    ) -> None:
        self.pages = pages
        self.details = details or {}
        self.calls: list[tuple[str, Any]] = []

    def search_positions(
        self,
        *,
        page_num: int,
        page_size: int,
        recruit_types: Sequence[str] = (),
        keyword: str = "",
        city_codes: Sequence[str] = (),
        job_types: Sequence[str] = (),
        share_id: str = "",
    ) -> OppoPositionPage:
        """Record one discovery request and return its configured page."""

        self.calls.append(
            (
                "search",
                {
                    "page_num": page_num,
                    "page_size": page_size,
                    "recruit_types": tuple(recruit_types),
                    "keyword": keyword,
                    "city_codes": tuple(city_codes),
                    "job_types": tuple(job_types),
                    "share_id": share_id,
                },
            )
        )
        result = self.pages[page_num]
        if isinstance(result, Exception):
            raise result
        return result

    def get_position_detail(
        self,
        position_id: str,
    ) -> OppoPositionDetail:
        """Record one detail request, raising configured failures."""

        self.calls.append(("detail", position_id))
        result = self.details[position_id]
        if isinstance(result, Exception):
            raise result
        return result


def make_crawler(
    source_client: FakeOppoJobSourceClient,
    **kwargs: Any,
) -> OppoJobCrawler:
    """Inject a network-free fake without widening production typing."""

    return OppoJobCrawler(source_client, **kwargs)  # type: ignore[arg-type]


def test_crawler_inherits_base_and_uses_stage_defaults() -> None:
    """The default query covers all daily internships without an AI keyword."""

    source_client = FakeOppoJobSourceClient(
        {1: position_page(1, 0, 0)}
    )
    crawler = make_crawler(source_client)

    assert isinstance(crawler, BaseJobCrawler)
    assert crawler.fetch_jobs() == []
    assert source_client.calls == [
        (
            "search",
            {
                "page_num": 1,
                "page_size": 20,
                "recruit_types": ("OFFEN-RECRUITMENT",),
                "keyword": "",
                "city_codes": (),
                "job_types": (),
                "share_id": "",
            },
        )
    ]


def test_explicit_filters_are_snapshotted_and_forwarded() -> None:
    """Caller-owned filter lists cannot mutate crawler configuration later."""

    recruit_types = ["SOCIAL-RECRUITMENT"]
    city_codes = ["44190X"]
    job_types = ["PRODUCT"]
    source_client = FakeOppoJobSourceClient(
        {1: position_page(1, 0, 0, page_size=7)}
    )
    crawler = make_crawler(
        source_client,
        recruit_types=recruit_types,
        keyword="AI",
        city_codes=city_codes,
        job_types=job_types,
        share_id="share-001",
        page_size=7,
    )
    recruit_types.append("OFFEN-RECRUITMENT")
    city_codes.append("44030X")
    job_types.append("TECHNOLOGY")

    assert crawler.fetch_jobs() == []
    assert source_client.calls[0][1] == {
        "page_num": 1,
        "page_size": 7,
        "recruit_types": ("SOCIAL-RECRUITMENT",),
        "keyword": "AI",
        "city_codes": ("44190X",),
        "job_types": ("PRODUCT",),
        "share_id": "share-001",
    }


@pytest.mark.parametrize("page_size", [True, False, 0, -1, 1.5, "20"])
def test_invalid_page_size_fails_before_source_calls(
    page_size: Any,
) -> None:
    """Only positive, non-boolean integers are accepted as page size."""

    source_client = FakeOppoJobSourceClient({})

    with pytest.raises(ValueError, match="page_size"):
        make_crawler(source_client, page_size=page_size)

    assert source_client.calls == []


def test_multi_page_discovery_precedes_sequential_detail_fetches() -> None:
    """Page-one bounds drive discovery before ordered detail requests."""

    source_client = FakeOppoJobSourceClient(
        {
            1: position_page(1, 2, 5, "position-001", "position-002"),
            2: position_page(2, 4, 1, "position-003"),
        },
        {
            value: position_detail(value)
            for value in (
                "position-001",
                "position-002",
                "position-003",
            )
        },
    )

    jobs = make_crawler(source_client).fetch_jobs()

    assert len(jobs) == 3
    assert [call[0] for call in source_client.calls] == [
        "search",
        "search",
        "detail",
        "detail",
        "detail",
    ]
    assert [
        call[1] for call in source_client.calls if call[0] == "detail"
    ] == ["position-001", "position-002", "position-003"]
    assert [
        call[1]["page_num"]
        for call in source_client.calls
        if call[0] == "search"
    ] == [1, 2]


def test_oppo_detail_maps_exactly_to_job_create() -> None:
    """Validated OPPO detail values map to the frozen JobCreate contract."""

    detail = position_detail("2061649545671430146")
    source_client = FakeOppoJobSourceClient(
        {1: position_page(1, 1, 1, detail.position_id)},
        {detail.position_id: detail},
    )

    jobs = make_crawler(source_client).fetch_jobs()

    assert [call[0] for call in source_client.calls] == [
        "search",
        "detail",
    ]
    assert jobs == [
        JobCreate(
            title="AI产品实习生",
            company="OPPO",
            city="东莞市",
            salary=None,
            description=(
                "岗位职责：\n负责产品调研与需求分析。\n\n"
                "任职要求：\n具备良好的沟通和分析能力。"
            ),
            skills=[],
            source="oppo",
            source_url=(
                "https://career.oppo.com/official/oppo/recruitment/post/"
                "2061649545671430146?recruitType=OFFEN-RECRUITMENT"
            ),
            published_at=date(2026, 6, 1),
        )
    ]


def test_detail_failure_is_fail_fast_and_stops_later_calls() -> None:
    """A failed detail prevents partial return and all later detail calls."""

    source_client = FakeOppoJobSourceClient(
        {1: position_page(1, 1, 3, "one", "two", "three")},
        {
            "one": position_detail("one"),
            "two": ValueError("malformed OPPO detail"),
            "three": position_detail("three"),
        },
    )

    with pytest.raises(ValueError, match="malformed OPPO detail"):
        make_crawler(source_client).fetch_jobs()

    assert source_client.calls[-2:] == [
        ("detail", "one"),
        ("detail", "two"),
    ]


def test_page_one_discovery_failure_stops_before_details() -> None:
    """A page-one discovery failure propagates without further calls."""

    failure = ValueError("discovery failed")
    source_client = FakeOppoJobSourceClient({1: failure})

    with pytest.raises(ValueError, match="discovery failed") as exc_info:
        make_crawler(source_client).fetch_jobs()

    assert exc_info.value is failure
    assert [call[0] for call in source_client.calls] == ["search"]
    assert source_client.calls[0][1]["page_num"] == 1


def test_later_discovery_failure_stops_pagination_before_details() -> None:
    """A later page failure prevents remaining pages and all details."""

    failure = ValueError("page 2 failed")
    source_client = FakeOppoJobSourceClient(
        {
            1: position_page(1, 3, 3, "one"),
            2: failure,
            3: position_page(3, 3, 3, "three"),
        },
        {"one": position_detail("one")},
    )

    with pytest.raises(ValueError, match="page 2 failed") as exc_info:
        make_crawler(source_client).fetch_jobs()

    assert exc_info.value is failure
    assert [call[0] for call in source_client.calls] == [
        "search",
        "search",
    ]
    assert [call[1]["page_num"] for call in source_client.calls] == [1, 2]
