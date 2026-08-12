"""Deterministic retry and API-error contract tests."""

from __future__ import annotations

import pytest
import requests
from singer_sdk.exceptions import RetriableAPIError

from tap_xero.client import XeroAPIError, XeroRateLimitError, XeroStream
from tap_xero.tap import TapXero

SAMPLE_CONFIG = {
    "oauth_credentials": {
        "client_id": "synthetic-client-id",
        "client_secret": "synthetic-client-secret",
        "refresh_token": "synthetic-refresh-token",
    },
    "tenant_id": "synthetic-tenant-id",
    "start_date": "2026-01-01T00:00:00Z",
    "include_archived_contacts": False,
}


@pytest.fixture
def stream() -> XeroStream:
    """Return a stream without authenticating or making an HTTP request."""
    return TapXero(config=SAMPLE_CONFIG).discover_streams()[0]


def response(
    status: int,
    *,
    headers: dict[str, str] | None = None,
    body: str = "",
) -> requests.Response:
    """Build a synthetic Requests response."""
    result = requests.Response()
    result.status_code = status
    result.headers.update(headers or {})
    result._content = body.encode()
    result.encoding = "utf-8"
    return result


def retry_wait(stream: XeroStream, error: Exception) -> int | float:
    """Send one exception through the SDK runtime-backoff generator."""
    generator = stream.backoff_wait_generator()
    next(generator)
    return generator.send(error)


@pytest.mark.parametrize(
    ("retry_after", "expected"),
    [("12", 12), ("9999", 60), ("0", 5), ("-1", 5), ("invalid", 5), (None, 5)],
)
def test_retry_wait_is_bounded(
    stream: XeroStream,
    retry_after: str | None,
    expected: int,
) -> None:
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    api_response = response(429, headers=headers)
    error = XeroRateLimitError("synthetic rate limit", response=api_response)

    assert retry_wait(stream, error) == expected


def test_retry_attempts_are_bounded(stream: XeroStream) -> None:
    assert stream.backoff_max_tries() == 5


def test_minute_rate_limit_is_retriable_with_a_bounded_wait(stream: XeroStream) -> None:
    api_response = response(
        429,
        headers={
            "Retry-After": "9999",
            "X-Rate-Limit-Problem": "Minute limit",
        },
    )

    with pytest.raises(XeroRateLimitError) as raised:
        stream.validate_response(api_response)

    assert raised.value.response is api_response
    assert "Retry-After: 60" in str(raised.value)


def test_daily_rate_limit_without_retry_header_is_not_retriable(stream: XeroStream) -> None:
    api_response = response(429, headers={"X-Rate-Limit-Problem": "Daily limit"})

    with pytest.raises(XeroAPIError, match="Cannot retry") as raised:
        stream.validate_response(api_response)

    assert raised.value.response is api_response


@pytest.mark.parametrize("status", [401, 500, 503])
def test_transient_statuses_remain_retriable(stream: XeroStream, status: int) -> None:
    with pytest.raises(RetriableAPIError) as raised:
        stream.validate_response(response(status))

    assert raised.value.response.status_code == status


def test_client_error_detail_is_normalised_and_bounded(stream: XeroStream) -> None:
    omitted_marker = "MUST-NOT-APPEAR"
    api_response = response(
        400,
        headers={"Content-Type": "application/json"},
        body='{"Message":"' + ("x" * 1_000) + omitted_marker + '"}',
    )

    with pytest.raises(XeroAPIError) as raised:
        stream.validate_response(api_response)

    message = str(raised.value)
    assert message.startswith("Client error 400: ")
    assert omitted_marker not in message
    assert len(message) <= 520
    assert raised.value.response is api_response
