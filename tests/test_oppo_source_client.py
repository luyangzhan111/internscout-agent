"""Network-free tests for the OPPO source HTTP boundary."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from copy import deepcopy
from datetime import date
import json
from typing import Any

import httpx
import pytest

from app.crawlers.oppo_source_client import (
    OppoJobSourceClient,
    OppoPositionDetail,
    OppoPositionPage,
    OppoPositionSummary,
)


DISCOVERY_URL = (
    "https://career.oppo.com/ats-candidate-api/open-api/position/"
    "queryPositionList"
)
DETAIL_URL = (
    "https://career.oppo.com/ats-candidate-api/open-api/position/"
    "queryPosition"
)


def valid_discovery_envelope() -> dict[str, Any]:
    """Return a fresh, valid discovery response envelope."""

    return {
        "code": "0",
        "msg": "success",
        "data": {
            "pageNum": 1,
            "pageSize": 20,
            "pages": 1,
            "total": 2,
            "list": [
                {"positionId": "position-001"},
                {"positionId": "position-002"},
            ],
        },
    }


def valid_detail_envelope() -> dict[str, Any]:
    """Return a fresh, valid position-detail response envelope."""

    return {
        "code": "0",
        "msg": "success",
        "data": {
            "positionId": "position-001",
            "publishName": "AI产品实习生",
            "publishDate": "2026-06-01",
            "recruitType": "OFFEN-RECRUITMENT",
            "workCityName": "东莞市",
            "jobDuty": "负责产品调研与需求分析。",
            "workRequire": "具备良好的沟通和分析能力。",
        },
    }


Handler = Callable[[httpx.Request], httpx.Response]


@contextmanager
def source_client(
    handler: Handler,
    *,
    timeout: float = 10.0,
) -> Iterator[OppoJobSourceClient]:
    """Build and close the caller-owned MockTransport HTTP client."""

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        yield OppoJobSourceClient(http_client, timeout=timeout)


def call_operation(
    client: OppoJobSourceClient,
    operation: str,
) -> OppoPositionPage | OppoPositionDetail:
    """Invoke one source operation for shared boundary-error tests."""

    if operation == "discovery":
        return client.search_positions(page_num=1, page_size=20)

    return client.get_position_detail("position-001")


def test_search_posts_expected_payload_and_returns_typed_page() -> None:
    captured_requests: list[httpx.Request] = []
    envelope = valid_discovery_envelope()
    envelope["data"].update({"pageNum": 2, "pageSize": 10, "pages": 3})

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, json=envelope)

    with source_client(handler) as client:
        page = client.search_positions(
            page_num=2,
            page_size=10,
            recruit_types=["SOCIAL-RECRUITMENT"],
            keyword="AI",
            city_codes=["44190X"],
            job_types=["PRODUCT"],
            share_id="share-001",
        )

    assert len(captured_requests) == 1
    request = captured_requests[0]
    assert request.method == "POST"
    assert str(request.url) == DISCOVERY_URL
    assert request.headers["content-type"].startswith("application/json")
    assert request.read()
    assert json.loads(request.content) == {
        "pageNum": 2,
        "pageSize": 10,
        "publishName": "AI",
        "workCityCodeList": ["44190X"],
        "jobTypeList": ["PRODUCT"],
        "recruitTypeList": ["SOCIAL-RECRUITMENT"],
        "shareId": "share-001",
    }
    assert page == OppoPositionPage(
        page_num=2,
        page_size=10,
        pages=3,
        total=2,
        positions=(
            OppoPositionSummary(position_id="position-001"),
            OppoPositionSummary(position_id="position-002"),
        ),
    )


def test_search_serializes_empty_optional_filters_without_source_policy() -> None:
    captured_payloads: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payloads.append(json.loads(request.content))
        return httpx.Response(200, json=valid_discovery_envelope())

    with source_client(handler) as client:
        client.search_positions(page_num=1, page_size=20)

    assert captured_payloads == [
        {
            "pageNum": 1,
            "pageSize": 20,
            "publishName": "",
            "workCityCodeList": [],
            "jobTypeList": [],
            "recruitTypeList": [],
            "shareId": "",
        }
    ]


@pytest.mark.parametrize("total_value", [1, "1"])
def test_search_accepts_integer_and_canonical_string_total(
    total_value: int | str,
) -> None:
    envelope = valid_discovery_envelope()
    envelope["data"].update(
        {
            "total": total_value,
            "list": [{"positionId": "position-001"}],
        }
    )

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        page = client.search_positions(page_num=1, page_size=20)

    assert page.total == 1
    assert type(page.total) is int


@pytest.mark.parametrize("total_value", [0, "0"])
def test_search_accepts_observed_empty_result_shape(
    total_value: int | str,
) -> None:
    envelope = valid_discovery_envelope()
    envelope["data"] = {
        "pageNum": 1,
        "pageSize": 20,
        "pages": 0,
        "total": total_value,
        "list": [],
    }

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        page = client.search_positions(page_num=1, page_size=20)

    assert page == OppoPositionPage(
        page_num=1,
        page_size=20,
        pages=0,
        total=0,
        positions=(),
    )
    assert type(page.total) is int


def test_detail_gets_expected_query_and_returns_typed_detail() -> None:
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, json=valid_detail_envelope())

    with source_client(handler) as client:
        detail = client.get_position_detail("position-001")

    assert len(captured_requests) == 1
    request = captured_requests[0]
    assert request.method == "GET"
    assert str(request.url.copy_with(query=None)) == DETAIL_URL
    assert dict(request.url.params) == {"positionId": "position-001"}
    assert detail == OppoPositionDetail(
        position_id="position-001",
        publish_name="AI产品实习生",
        publish_date=date(2026, 6, 1),
        recruit_type="OFFEN-RECRUITMENT",
        work_city_name="东莞市",
        job_duty="负责产品调研与需求分析。",
        work_require="具备良好的沟通和分析能力。",
    )


def test_blank_detail_position_id_fails_before_http_request() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise AssertionError("blank input must not reach the transport")

    with source_client(handler) as client:
        with pytest.raises(ValueError, match="position_id"):
            client.get_position_detail("   ")

    assert attempts == 0


@pytest.mark.parametrize("operation", ["discovery", "detail"])
def test_transport_failure_propagates_without_retry(operation: str) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("source unavailable", request=request)

    with source_client(handler) as client:
        with pytest.raises(httpx.ConnectError, match="source unavailable"):
            call_operation(client, operation)

    assert attempts == 1


@pytest.mark.parametrize("operation", ["discovery", "detail"])
def test_http_status_failure_propagates_without_retry(operation: str) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"message": "unavailable"})

    with source_client(handler) as client:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            call_operation(client, operation)

    assert exc_info.value.response.status_code == 503
    assert attempts == 1


@pytest.mark.parametrize("operation", ["discovery", "detail"])
def test_invalid_json_becomes_contextual_value_error(operation: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"{not-json",
            headers={"content-type": "application/json"},
        )

    with source_client(handler) as client:
        with pytest.raises(ValueError, match=f"OPPO {operation}.*JSON"):
            call_operation(client, operation)


@pytest.mark.parametrize("operation", ["discovery", "detail"])
@pytest.mark.parametrize(
    ("response_json", "message"),
    [
        (["not", "an", "object"], "object"),
        ({"data": {}}, "code"),
        ({"code": 1, "data": {}}, "code"),
        ({"code": 0}, "data"),
        ({"code": 0, "data": []}, "data"),
    ],
)
def test_invalid_envelope_fails_contextually(
    operation: str,
    response_json: Any,
    message: str,
) -> None:
    with source_client(
        lambda request: httpx.Response(200, json=response_json)
    ) as client:
        with pytest.raises(
            ValueError,
            match=f"OPPO {operation}.*{message}",
        ):
            call_operation(client, operation)


@pytest.mark.parametrize("operation", ["discovery", "detail"])
@pytest.mark.parametrize("success_code", [0, "0"])
def test_observed_success_codes_are_accepted(
    operation: str,
    success_code: int | str,
) -> None:
    envelope = (
        valid_discovery_envelope()
        if operation == "discovery"
        else valid_detail_envelope()
    )
    envelope["code"] = success_code

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        result = call_operation(client, operation)

    if operation == "discovery":
        assert isinstance(result, OppoPositionPage)
    else:
        assert isinstance(result, OppoPositionDetail)


@pytest.mark.parametrize("operation", ["discovery", "detail"])
@pytest.mark.parametrize(
    "invalid_code",
    [False, None, "", "zero", "00", " 0", 0.0, [], {}],
)
def test_malformed_code_fails(
    operation: str,
    invalid_code: Any,
) -> None:
    envelope = (
        valid_discovery_envelope()
        if operation == "discovery"
        else valid_detail_envelope()
    )
    envelope["code"] = invalid_code

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(ValueError, match=f"OPPO {operation}.*code"):
            call_operation(client, operation)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("pageNum", 0),
        ("pageNum", True),
        ("pageNum", "1"),
        ("pageSize", 0),
        ("pageSize", False),
        ("pageSize", "20"),
        ("pages", -1),
        ("pages", True),
        ("pages", "1"),
    ],
)
def test_invalid_discovery_integer_metadata_fails(
    field: str,
    invalid_value: Any,
) -> None:
    envelope = valid_discovery_envelope()
    envelope["data"][field] = invalid_value

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(ValueError, match=f"discovery.*{field}"):
            client.search_positions(page_num=1, page_size=20)


@pytest.mark.parametrize(
    "invalid_total",
    [
        "",
        " ",
        " 1",
        "1 ",
        "+1",
        "-1",
        "1.0",
        "01",
        "00",
        "1e3",
        "zero",
        "１２",
    ],
)
def test_malformed_string_total_fails(invalid_total: str) -> None:
    envelope = valid_discovery_envelope()
    envelope["data"]["total"] = invalid_total

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(ValueError, match="discovery.*total"):
            client.search_positions(page_num=1, page_size=20)


@pytest.mark.parametrize(
    "invalid_total",
    [False, True, None, 1.0, [], {}],
)
def test_malformed_non_integer_total_fails(invalid_total: Any) -> None:
    envelope = valid_discovery_envelope()
    envelope["data"]["total"] = invalid_total

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(ValueError, match="discovery.*total"):
            client.search_positions(page_num=1, page_size=20)


def test_negative_integer_total_fails() -> None:
    envelope = valid_discovery_envelope()
    envelope["data"]["total"] = -1

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(ValueError, match="discovery.*total"):
            client.search_positions(page_num=1, page_size=20)


def test_non_list_discovery_list_fails() -> None:
    envelope = valid_discovery_envelope()
    envelope["data"]["list"] = {"positionId": "position-001"}

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(ValueError, match="discovery.*list"):
            client.search_positions(page_num=1, page_size=20)


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"pages": 0, "total": 1, "list": []}, "pages"),
        (
            {
                "pages": 0,
                "total": 0,
                "list": [{"positionId": "position-001"}],
            },
            "pages",
        ),
        ({"pageNum": 2, "pages": 1}, "pageNum"),
    ],
)
def test_contradictory_discovery_pagination_fails(
    updates: dict[str, Any],
    message: str,
) -> None:
    envelope = valid_discovery_envelope()
    envelope["data"].update(updates)

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(ValueError, match=f"discovery.*{message}"):
            client.search_positions(page_num=1, page_size=20)


def test_positive_pages_with_zero_total_fails() -> None:
    envelope = valid_discovery_envelope()
    envelope["data"].update(
        {"pages": 1, "total": "0", "list": []}
    )

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(ValueError, match="discovery.*pages.*total"):
            client.search_positions(page_num=1, page_size=20)


@pytest.mark.parametrize(
    ("pages", "total", "position_count"),
    [
        (1, 21, 20),
        (1, 1, 0),
        (2, 41, 20),
        (2, "40", 19),
    ],
)
def test_impossible_discovery_capacity_fails(
    pages: int,
    total: int | str,
    position_count: int,
) -> None:
    envelope = valid_discovery_envelope()
    envelope["data"].update(
        {
            "pages": pages,
            "total": total,
            "list": [
                {"positionId": f"position-{index}"}
                for index in range(position_count)
            ],
        }
    )

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(
            ValueError,
            match="discovery.*total.*capacity",
        ):
            client.search_positions(page_num=1, page_size=20)


def test_non_full_discovery_page_with_sufficient_capacity_is_valid() -> None:
    envelope = valid_discovery_envelope()
    envelope["data"].update(
        {
            "pages": 2,
            "total": 21,
            "list": [{"positionId": "position-001"}],
        }
    )

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        page = client.search_positions(page_num=1, page_size=20)

    assert page.pages == 2
    assert page.total == 21
    assert page.positions == (
        OppoPositionSummary(position_id="position-001"),
    )


def test_discovery_list_longer_than_total_fails() -> None:
    envelope = valid_discovery_envelope()
    envelope["data"]["total"] = "1"

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(ValueError, match="discovery.*list.*total"):
            client.search_positions(page_num=1, page_size=20)


def test_returned_page_number_must_match_requested_page() -> None:
    envelope = valid_discovery_envelope()
    envelope["data"].update({"pageNum": 1, "pages": 2})

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(
            ValueError,
            match="discovery.*pageNum.*requested",
        ):
            client.search_positions(page_num=2, page_size=20)


def test_discovery_list_longer_than_page_size_fails() -> None:
    envelope = valid_discovery_envelope()
    envelope["data"].update({"pageSize": 1, "pages": 2})

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(ValueError, match="discovery.*pageSize"):
            client.search_positions(page_num=1, page_size=1)


@pytest.mark.parametrize(
    "item",
    [
        {},
        {"positionId": "   "},
        {"positionId": 123},
        "not-an-object",
    ],
)
def test_malformed_discovery_position_id_fails(item: Any) -> None:
    envelope = valid_discovery_envelope()
    envelope["data"].update({"total": 1, "list": [item]})

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(ValueError, match="discovery.*positionId"):
            client.search_positions(page_num=1, page_size=20)


@pytest.mark.parametrize(
    "field",
    [
        "positionId",
        "publishName",
        "publishDate",
        "recruitType",
        "workCityName",
        "jobDuty",
        "workRequire",
    ],
)
def test_missing_required_detail_field_fails(field: str) -> None:
    envelope = valid_detail_envelope()
    del envelope["data"][field]

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(ValueError, match=f"detail.*{field}"):
            client.get_position_detail("position-001")


@pytest.mark.parametrize(
    "field",
    [
        "positionId",
        "publishName",
        "publishDate",
        "recruitType",
        "workCityName",
        "jobDuty",
        "workRequire",
    ],
)
def test_blank_required_detail_field_fails(field: str) -> None:
    envelope = valid_detail_envelope()
    envelope["data"][field] = "   "

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(ValueError, match=f"detail.*{field}"):
            client.get_position_detail("position-001")


@pytest.mark.parametrize(
    "field",
    [
        "positionId",
        "publishName",
        "publishDate",
        "recruitType",
        "workCityName",
        "jobDuty",
        "workRequire",
    ],
)
def test_wrong_required_detail_field_type_fails(field: str) -> None:
    envelope = valid_detail_envelope()
    envelope["data"][field] = 123

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(ValueError, match=f"detail.*{field}"):
            client.get_position_detail("position-001")


@pytest.mark.parametrize(
    "invalid_date",
    ["2026-02-30", "2026/06/01", "June 1, 2026", "2026-06-01T00:00:00"],
)
def test_invalid_publish_date_fails(invalid_date: str) -> None:
    envelope = valid_detail_envelope()
    envelope["data"]["publishDate"] = invalid_date

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(ValueError, match="detail.*publishDate"):
            client.get_position_detail("position-001")


def test_returned_position_id_mismatch_fails() -> None:
    envelope = deepcopy(valid_detail_envelope())
    envelope["data"]["positionId"] = "different-position"

    with source_client(
        lambda request: httpx.Response(200, json=envelope)
    ) as client:
        with pytest.raises(ValueError, match="detail.*positionId.*match"):
            client.get_position_detail("position-001")
