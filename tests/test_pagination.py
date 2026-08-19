"""Behavioural tests for paginated stream page tokens."""

import datetime
import json

import pytest
import requests

from tap_xero import streams
from tap_xero.tap import TapXero

SAMPLE_CONFIG = {
    "oauth_credentials": {
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "refresh_token": "test_refresh_token",
    },
    "tenant_id": "test-tenant-id-pagination",
    "start_date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}

PAGINATED_STREAM_CLASSES = sorted(
    (
        cls
        for cls in vars(streams).values()
        if isinstance(cls, type)
        and issubclass(cls, streams.PaginatedStream)
        and cls is not streams.PaginatedStream
    ),
    key=lambda cls: cls.name,
)


def records_key(stream_class: type[streams.PaginatedStream]) -> str:
    """Return the Xero envelope key holding the records for a stream."""
    return stream_class.records_jsonpath.removeprefix("$.").removesuffix("[*]")


def build_response(
    stream_class: type[streams.PaginatedStream], record_count: int
) -> requests.Response:
    """Build a Xero-shaped response envelope holding ``record_count`` records."""
    key = records_key(stream_class)
    payload = {
        # Xero wraps every collection in these envelope fields, none of which are records.
        "Id": "8e5b1b1a-0000-4000-8000-000000000000",
        "Status": "OK",
        "ProviderName": "tap-xero-test",
        "DateTimeUTC": "/Date(1740000000000)/",
        key: [{"Name": f"record-{i}"} for i in range(record_count)],
    }

    response = requests.Response()
    response.status_code = 200
    response.headers["Content-Type"] = "application/json"
    response._content = json.dumps(payload).encode()
    return response


@pytest.fixture(scope="module")
def tap() -> TapXero:
    """Return a tap configured for standard OAuth."""
    return TapXero(config=SAMPLE_CONFIG)


@pytest.mark.parametrize("stream_class", PAGINATED_STREAM_CLASSES, ids=lambda cls: cls.name)
def test_full_page_yields_next_page_token(tap: TapXero, stream_class) -> None:
    """A full page must advance the page number so later pages are actually fetched."""
    stream = stream_class(tap)
    response = build_response(stream_class, stream.page_size)

    assert stream.get_next_page_token(response, None) == 2
    assert stream.get_next_page_token(response, 2) == 3


@pytest.mark.parametrize("stream_class", PAGINATED_STREAM_CLASSES, ids=lambda cls: cls.name)
def test_partial_page_ends_pagination(tap: TapXero, stream_class) -> None:
    """A partial page is the last page, so no further token is issued."""
    stream = stream_class(tap)
    response = build_response(stream_class, stream.page_size - 1)

    assert stream.get_next_page_token(response, None) is None
    assert stream.get_next_page_token(response, 2) is None


def test_all_paginated_streams_are_covered() -> None:
    """Guard against a new paginated stream slipping past these tests."""
    assert len(PAGINATED_STREAM_CLASSES) == 10
