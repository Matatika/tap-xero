"""Deterministic retry and API-error contract tests."""

from __future__ import annotations

import time

import pytest
import requests
from singer_sdk.exceptions import RetriableAPIError

from tap_xero.client import (
    DEFAULT_RETRY_WAIT_SECONDS,
    MAX_RETRY_WAIT_SECONDS,
    XeroAPIError,
    XeroRateLimitError,
    XeroStream,
)
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


def drive_decorated_request(
    stream: XeroStream,
    monkeypatch: pytest.MonkeyPatch,
    api_response: requests.Response,
) -> tuple[list[requests.PreparedRequest], list[float]]:
    """Drive the real decorated request path until it gives up.

    Returns the requests actually sent and the waits actually taken, so the retry
    ceiling is measured through ``request_decorator`` rather than asserted against
    the constant that defines it.
    """
    sent: list[requests.PreparedRequest] = []
    waits: list[float] = []

    def send(prepared_request: requests.PreparedRequest, **_kwargs: object) -> requests.Response:
        sent.append(prepared_request)
        return api_response

    monkeypatch.setattr(time, "sleep", waits.append)
    monkeypatch.setattr(stream.requests_session, "send", send)
    # `authenticator` is a cached_property, so seeding it avoids a real token refresh.
    stream.__dict__["authenticator"] = lambda prepared_request: prepared_request

    decorated_request = stream.request_decorator(stream._request)
    prepared = requests.Request("GET", f"{stream.url_base}{stream.path}").prepare()

    with pytest.raises(RetriableAPIError):
        decorated_request(prepared, None)

    return sent, waits


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


def test_retry_attempts_are_bounded(stream: XeroStream, monkeypatch: pytest.MonkeyPatch) -> None:
    """A permanently failing endpoint is attempted five times, then gives up."""
    sent, waits = drive_decorated_request(stream, monkeypatch, response(503))

    assert len(sent) == 5
    assert len(waits) == 4
    # `random_jitter` adds up to one second on top of each bounded wait.
    assert all(DEFAULT_RETRY_WAIT_SECONDS <= wait < MAX_RETRY_WAIT_SECONDS + 1 for wait in waits)


def test_retry_ceiling_is_taken_from_backoff_max_tries(
    stream: XeroStream,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ceiling has to reach the decorator, not just exist on the stream."""
    monkeypatch.setattr(stream, "backoff_max_tries", lambda: 2)

    sent, waits = drive_decorated_request(stream, monkeypatch, response(503))

    assert len(sent) == 2
    assert len(waits) == 1


def test_retry_after_header_reaches_the_decorator(
    stream: XeroStream,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wait the generator derives from Retry-After is the wait actually taken."""
    sent, waits = drive_decorated_request(
        stream,
        monkeypatch,
        response(429, headers={"Retry-After": "12"}),
    )

    assert len(sent) == 5
    assert all(12 <= wait < 13 for wait in waits)


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


@pytest.mark.parametrize(
    ("content_type", "body", "expected"),
    [
        pytest.param(
            "text/html",
            "<html>Bad   Request</html>",
            "Client error 400: <html>Bad Request</html>",
            id="non-json-body",
        ),
        pytest.param(
            "application/json",
            "not json at all",
            "Client error 400: not json at all",
            id="malformed-json-body",
        ),
        pytest.param(
            "application/json",
            '["Message", "ignored"]',
            'Client error 400: ["Message", "ignored"]',
            id="json-array-body",
        ),
        pytest.param(
            "application/json",
            '{"Detail": "no Message key"}',
            'Client error 400: {"Detail": "no Message key"}',
            id="json-without-message",
        ),
        pytest.param("text/plain", "   ", "Client error 400", id="blank-body"),
        pytest.param("text/plain", "", "Client error 400", id="empty-body"),
    ],
)
def test_client_error_detail_falls_back_to_the_response_body(
    stream: XeroStream,
    content_type: str,
    body: str,
    expected: str,
) -> None:
    """A 4xx body the tap cannot read as a Xero error still has to say something."""
    api_response = response(400, headers={"Content-Type": content_type}, body=body)

    with pytest.raises(XeroAPIError) as raised:
        stream.validate_response(api_response)

    assert str(raised.value) == expected
    assert raised.value.response is api_response


def test_client_error_body_fallback_is_bounded(stream: XeroStream) -> None:
    """The response-text fallback is bounded the same way the parsed detail is."""
    omitted_marker = "MUST-NOT-APPEAR"
    api_response = response(
        400,
        headers={"Content-Type": "text/html"},
        body=("y" * 1_000) + omitted_marker,
    )

    with pytest.raises(XeroAPIError) as raised:
        stream.validate_response(api_response)

    message = str(raised.value)
    assert message.startswith("Client error 400: ")
    assert omitted_marker not in message
    assert len(message) <= 520
