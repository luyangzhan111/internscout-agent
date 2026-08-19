"""HTTP boundary for OPPO recruitment website position data."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
import math
from typing import Any

import httpx


DISCOVERY_URL = (
    "https://career.oppo.com/ats-candidate-api/open-api/position/"
    "queryPositionList"
)
DETAIL_URL = (
    "https://career.oppo.com/ats-candidate-api/open-api/position/"
    "queryPosition"
)
DEFAULT_TIMEOUT_SECONDS = 10.0

_MISSING = object()


@dataclass(frozen=True, slots=True)
class OppoPositionSummary:
    """Minimum discovery data needed to identify one OPPO position."""

    position_id: str


@dataclass(frozen=True, slots=True)
class OppoPositionPage:
    """One validated page returned by OPPO position discovery."""

    page_num: int
    page_size: int
    pages: int
    total: int
    positions: tuple[OppoPositionSummary, ...]


@dataclass(frozen=True, slots=True)
class OppoPositionDetail:
    """Mapping-critical values from one OPPO position detail."""

    position_id: str
    publish_name: str
    publish_date: date
    recruit_type: str
    work_city_name: str
    job_duty: str
    work_require: str


class OppoJobSourceClient:
    """Read and validate OPPO position JSON through an injected client."""

    DISCOVERY_URL = DISCOVERY_URL
    DETAIL_URL = DETAIL_URL

    def __init__(
        self,
        http_client: httpx.Client,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """Store a caller-owned synchronous HTTP client and timeout policy."""

        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("timeout must be a positive finite number")

        self._http_client = http_client
        self._timeout = float(timeout)

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
        """Request and return exactly one validated discovery page."""

        self._validate_positive_request_integer(page_num, "page_num")
        self._validate_positive_request_integer(page_size, "page_size")

        response = self._http_client.post(
            self.DISCOVERY_URL,
            json={
                "pageNum": page_num,
                "pageSize": page_size,
                "publishName": keyword,
                "workCityCodeList": list(city_codes),
                "jobTypeList": list(job_types),
                "recruitTypeList": list(recruit_types),
                "shareId": share_id,
            },
            timeout=self._timeout,
        )
        data = self._decode_data(response, operation="discovery")

        returned_page_num = self._required_integer(
            data,
            "pageNum",
            minimum=1,
            operation="discovery",
        )
        returned_page_size = self._required_integer(
            data,
            "pageSize",
            minimum=1,
            operation="discovery",
        )
        pages = self._required_integer(
            data,
            "pages",
            minimum=0,
            operation="discovery",
        )
        total = self._required_non_negative_count(
            data,
            "total",
            operation="discovery",
        )
        raw_positions = data.get("list", _MISSING)

        if not isinstance(raw_positions, list):
            raise ValueError("OPPO discovery data.list must be a list")

        if pages == 0 and (total != 0 or raw_positions):
            raise ValueError(
                "OPPO discovery data has contradictory pages=0 metadata"
            )

        if pages > 0 and total == 0:
            raise ValueError(
                "OPPO discovery data.pages cannot be positive when "
                "data.total is zero"
            )

        if returned_page_num != page_num:
            raise ValueError(
                "OPPO discovery data.pageNum does not match the requested "
                "page_num"
            )

        if pages > 0 and returned_page_num > pages:
            raise ValueError(
                "OPPO discovery data.pageNum must not exceed data.pages"
            )

        if len(raw_positions) > total:
            raise ValueError(
                "OPPO discovery data.list must not exceed data.total"
            )

        if len(raw_positions) > returned_page_size:
            raise ValueError(
                "OPPO discovery data.list must not exceed data.pageSize"
            )

        positions = tuple(
            self._parse_position_summary(item, index)
            for index, item in enumerate(raw_positions, start=1)
        )

        return OppoPositionPage(
            page_num=returned_page_num,
            page_size=returned_page_size,
            pages=pages,
            total=total,
            positions=positions,
        )

    def get_position_detail(
        self,
        position_id: str,
    ) -> OppoPositionDetail:
        """Request and return one validated position detail."""

        requested_position_id = self._nonblank_string(
            position_id,
            "requested position_id",
            operation="detail",
        )
        response = self._http_client.get(
            self.DETAIL_URL,
            params={"positionId": requested_position_id},
            timeout=self._timeout,
        )
        data = self._decode_data(response, operation="detail")

        returned_position_id = self._required_string(
            data,
            "positionId",
            operation="detail",
        )
        if returned_position_id != requested_position_id:
            raise ValueError(
                "OPPO detail data.positionId does not match the requested "
                "position_id"
            )

        publish_date_text = self._required_string(
            data,
            "publishDate",
            operation="detail",
        )
        publish_date = self._parse_publish_date(publish_date_text)

        return OppoPositionDetail(
            position_id=returned_position_id,
            publish_name=self._required_string(
                data,
                "publishName",
                operation="detail",
            ),
            publish_date=publish_date,
            recruit_type=self._required_string(
                data,
                "recruitType",
                operation="detail",
            ),
            work_city_name=self._required_string(
                data,
                "workCityName",
                operation="detail",
            ),
            job_duty=self._required_string(
                data,
                "jobDuty",
                operation="detail",
            ),
            work_require=self._required_string(
                data,
                "workRequire",
                operation="detail",
            ),
        )

    @staticmethod
    def _decode_data(
        response: httpx.Response,
        *,
        operation: str,
    ) -> Mapping[str, Any]:
        """Raise for HTTP failures, then validate a source response envelope."""

        response.raise_for_status()

        try:
            envelope = response.json()
        except ValueError as exc:
            raise ValueError(
                f"OPPO {operation} response contains invalid JSON"
            ) from exc

        if not isinstance(envelope, Mapping):
            raise ValueError(
                f"OPPO {operation} JSON root must be an object"
            )

        code = envelope.get("code", _MISSING)
        if code is _MISSING:
            raise ValueError(f"OPPO {operation} response is missing code")
        if isinstance(code, bool):
            raise ValueError(
                f"OPPO {operation} response code must be integer 0 "
                'or string "0"'
            )
        if code == "0":
            code = 0
        elif not isinstance(code, int):
            raise ValueError(
                f"OPPO {operation} response code must be integer 0 "
                'or string "0"'
            )
        if code != 0:
            raise ValueError(
                f"OPPO {operation} response returned nonzero code {code}"
            )

        data = envelope.get("data", _MISSING)
        if data is _MISSING:
            raise ValueError(f"OPPO {operation} response is missing data")
        if not isinstance(data, Mapping):
            raise ValueError(
                f"OPPO {operation} response data must be an object"
            )

        return data

    @classmethod
    def _parse_position_summary(
        cls,
        item: Any,
        index: int,
    ) -> OppoPositionSummary:
        """Validate one discovery item without skipping malformed values."""

        if not isinstance(item, Mapping):
            raise ValueError(
                "OPPO discovery data.list item "
                f"{index} must be an object containing positionId"
            )

        return OppoPositionSummary(
            position_id=cls._required_string(
                item,
                "positionId",
                operation=f"discovery item {index}",
            )
        )

    @classmethod
    def _required_string(
        cls,
        data: Mapping[str, Any],
        field: str,
        *,
        operation: str,
    ) -> str:
        """Read one required, nonblank string from source data."""

        value = data.get(field, _MISSING)
        if value is _MISSING:
            raise ValueError(
                f"OPPO {operation} data is missing {field}"
            )

        return cls._nonblank_string(
            value,
            field,
            operation=operation,
        )

    @staticmethod
    def _nonblank_string(
        value: Any,
        field: str,
        *,
        operation: str,
    ) -> str:
        """Validate and normalize a source string value."""

        if not isinstance(value, str):
            raise ValueError(
                f"OPPO {operation} {field} must be a string"
            )

        normalized = value.strip()
        if not normalized:
            raise ValueError(
                f"OPPO {operation} {field} must be nonblank"
            )

        return normalized

    @staticmethod
    def _required_integer(
        data: Mapping[str, Any],
        field: str,
        *,
        minimum: int,
        operation: str,
    ) -> int:
        """Read one required source integer with a lower bound."""

        value = data.get(field, _MISSING)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(
                f"OPPO {operation} data.{field} must be an integer"
            )
        if value < minimum:
            raise ValueError(
                f"OPPO {operation} data.{field} must be at least {minimum}"
            )

        return value

    @staticmethod
    def _required_non_negative_count(
        data: Mapping[str, Any],
        field: str,
        *,
        operation: str,
    ) -> int:
        """Read an integer count or its canonical ASCII decimal string."""

        value = data.get(field, _MISSING)

        if isinstance(value, bool):
            raise ValueError(
                f"OPPO {operation} data.{field} must be a non-negative "
                "integer or canonical decimal string"
            )

        if isinstance(value, int):
            if value < 0:
                raise ValueError(
                    f"OPPO {operation} data.{field} must be at least 0"
                )

            return value

        if isinstance(value, str):
            is_canonical_decimal = value == "0" or (
                bool(value)
                and value[0] in "123456789"
                and all(character in "0123456789" for character in value[1:])
            )
            if is_canonical_decimal:
                return int(value)

        raise ValueError(
            f"OPPO {operation} data.{field} must be a non-negative "
            "integer or canonical decimal string"
        )

    @staticmethod
    def _validate_positive_request_integer(
        value: Any,
        field: str,
    ) -> None:
        """Reject unusable discovery pagination input before HTTP."""

        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{field} must be an integer of at least 1")

    @staticmethod
    def _parse_publish_date(value: str) -> date:
        """Parse only the verified YYYY-MM-DD publication date shape."""

        has_iso_shape = (
            len(value) == 10
            and value[4] == "-"
            and value[7] == "-"
            and value[:4].isdigit()
            and value[5:7].isdigit()
            and value[8:].isdigit()
        )
        if not has_iso_shape:
            raise ValueError(
                "OPPO detail data.publishDate must use YYYY-MM-DD"
            )

        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                "OPPO detail data.publishDate is not a valid date"
            ) from exc
