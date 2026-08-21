"""HTTP client for the Streamlit Demo to call the FastAPI Backend."""

import os
from typing import Any

import httpx
from pydantic import ValidationError

from demo.contracts import DemoAgentResponse


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 60.0
API_BASE_URL_ENV = "INTERNSCOUT_API_BASE_URL"
API_TIMEOUT_ENV = "INTERNSCOUT_API_TIMEOUT_SECONDS"


class DemoClientError(Exception):
    """Base error for failures visible at the Demo boundary."""


class BackendTimeoutError(DemoClientError):
    """The Backend did not respond within the configured timeout."""


class BackendUnavailableError(DemoClientError):
    """The Backend could not be reached or returned a server error."""


class BackendRequestError(DemoClientError):
    """The Backend rejected the Demo request."""


class BackendResponseError(DemoClientError):
    """The Backend response was not valid for the Demo contract."""


def build_query_payload(user_message: str) -> dict[str, Any]:
    """Build the opt-in request consumed by the existing Agent endpoint."""

    normalized_message = user_message.strip()
    if not normalized_message:
        raise ValueError("user_message cannot be blank.")

    return {
        "user_message": normalized_message,
        "include_recommendations": True,
    }


class AgentApiClient:
    """Small synchronous HTTP client for one independent Agent query."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_API_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        normalized_base_url = base_url.strip().rstrip("/")
        if not normalized_base_url:
            raise ValueError("base_url cannot be blank.")
        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

        self._base_url = normalized_base_url
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    @classmethod
    def from_env(cls) -> "AgentApiClient":
        """Create a client from Demo-local environment configuration."""

        base_url = os.getenv(
            API_BASE_URL_ENV,
            DEFAULT_API_BASE_URL,
        )
        timeout_value = os.getenv(
            API_TIMEOUT_ENV,
            str(DEFAULT_TIMEOUT_SECONDS),
        )

        try:
            timeout_seconds = float(timeout_value)
        except ValueError as exc:
            raise ValueError(
                f"{API_TIMEOUT_ENV} must be a number."
            ) from exc

        return cls(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )

    def query(self, user_message: str) -> DemoAgentResponse:
        """Submit one query and validate the public Backend response."""

        payload = build_query_payload(user_message)

        try:
            with httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.post(
                    "/api/agent/query",
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise BackendTimeoutError(
                "Backend request timed out."
            ) from exc
        except httpx.RequestError as exc:
            raise BackendUnavailableError(
                "Backend is unavailable."
            ) from exc

        if response.status_code >= 500:
            raise BackendUnavailableError(
                "Backend service is unavailable."
            )

        if response.status_code >= 400:
            raise BackendRequestError(
                self._format_request_error(response)
            )

        try:
            response_data = response.json()
        except ValueError as exc:
            raise BackendResponseError(
                "Backend returned invalid JSON."
            ) from exc

        try:
            return DemoAgentResponse.model_validate(
                response_data
            )
        except ValidationError as exc:
            raise BackendResponseError(
                "Backend response does not match the Demo contract."
            ) from exc

    @staticmethod
    def _format_request_error(response: httpx.Response) -> str:
        """Convert a client-visible HTTP error into a safe message."""

        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None

        if isinstance(detail, str) and detail.strip():
            return detail.strip()

        return (
            "Backend rejected the request "
            f"(HTTP {response.status_code})."
        )
