"""Tests standard tap features using the built-in SDK tests library."""

import datetime
import re
from collections.abc import Iterator

import pytest
import responses
from singer_sdk.testing import SuiteConfig, get_tap_test_class

from tap_xero.tap import TapXero

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

XERO_API_URL = re.compile(r"https://api\.xero\.com/api\.xro/2\.0/.*")


@pytest.fixture(scope="class", autouse=True)
def mock_xero_requests() -> Iterator[None]:
    """Mock Xero so SDK conformance tests do not require live credentials."""
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mocked:
        mocked.add(
            responses.POST,
            "https://identity.xero.com/connect/token",
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
            callback=lambda _request: (200, {"Content-Type": "application/json"}, "{}"),
        )
        yield


# Run standard built-in tap tests from the SDK:
TestTapXero = get_tap_test_class(
    tap_class=TapXero,
    config=SAMPLE_CONFIG,
    suite_config=SuiteConfig(ignore_no_records=True),
)
