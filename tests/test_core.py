"""Tests standard tap features using the built-in SDK tests library."""

from __future__ import annotations

import datetime
import json
import re
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import pytest
import responses
from singer_sdk.testing import get_tap_test_class

from tap_xero.auth import ProxyXeroOAuth2Authenticator, XeroOAuth2Authenticator
from tap_xero.tap import TapXero
from tests.xero_fixtures import XERO_RESPONSES

if TYPE_CHECKING:
    from collections.abc import Iterator

    from requests import PreparedRequest

SAMPLE_CONFIG = {
    "oauth_credentials": {
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "refresh_token": "test_refresh_token",
    },
    "tenant_id": "test_realm_id",
    "start_date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "include_archived_contacts": False,
}

TOKEN_URL = "https://identity.xero.com/connect/token"
XERO_API_URL = re.compile(r"https://api\.xero\.com/api\.xro/2\.0/.*")

# SingletonMeta stores the shared instance under this name-mangled class attribute.
_SINGLETON_ATTR = "_SingletonMeta__single_instance"


def reset_authenticator_singletons() -> None:
    """Drop the process-wide authenticator singletons.

    ``SingletonMeta`` caches one instance per class for the life of the process, so
    without this reset an authenticator built by another test module is reused here and
    the mocked token refresh below is never exercised.
    """
    for authenticator_class in (XeroOAuth2Authenticator, ProxyXeroOAuth2Authenticator):
        setattr(authenticator_class, _SINGLETON_ATTR, None)


def page_records(endpoint: str, query: dict[str, list[str]]) -> list[dict]:
    """Return the fixture records Xero would serve for this endpoint and query."""
    records = XERO_RESPONSES[endpoint]

    if endpoint == "Journals":
        # Journals are paged by JournalNumber rather than page number. The tap sends the
        # configured start_date on the first request, which is not a journal number, so
        # anything non-numeric means "from the beginning".
        raw_offset = query.get("offset", ["0"])[0]
        offset = int(raw_offset) if raw_offset.isdigit() else 0
        return [record for record in records if record["JournalNumber"] > offset]

    # Xero returns an empty collection once the caller walks past the last page.
    return [] if int(query.get("page", ["1"])[0]) > 1 else records


def xero_api_callback(request: PreparedRequest) -> tuple[int, dict[str, str], str]:
    """Serve the fixture records for the requested Xero endpoint."""
    url = urlparse(str(request.url))
    endpoint = url.path.rsplit("/", 1)[-1]
    records = page_records(endpoint, parse_qs(url.query))

    body = {
        "Id": "8e5b1b1a-0000-4000-8000-000000000000",
        "Status": "OK",
        "ProviderName": "tap-xero-test",
        "DateTimeUTC": "/Date(1704070800000+0000)/",
        endpoint: records,
    }
    return 200, {"Content-Type": "application/json"}, json.dumps(body)


@pytest.fixture(scope="class", autouse=True)
def mock_xero_requests() -> Iterator[None]:
    """Mock Xero so SDK conformance tests do not require live credentials."""
    reset_authenticator_singletons()

    with responses.RequestsMock() as mocked:
        mocked.add(
            responses.POST,
            TOKEN_URL,
            json={
                "access_token": "test_access_token",
                "expires_in": 3600,
                "refresh_token": "test_refresh_token",
            },
            status=200,
        )
        mocked.add_callback(
            responses.GET,
            XERO_API_URL,
            callback=xero_api_callback,
        )
        yield

        # Covering the OAuth exchange is the point of this suite, so prove it happened
        # instead of letting an unused mock go unnoticed.
        token_calls = [call for call in mocked.calls if call.request.url == TOKEN_URL]
        assert token_calls, "OAuth token endpoint was never called during the sync."

    reset_authenticator_singletons()


# Run standard built-in tap tests from the SDK:
TestTapXero = get_tap_test_class(
    tap_class=TapXero,
    config=SAMPLE_CONFIG,
)
