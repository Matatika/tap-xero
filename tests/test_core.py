"""Tests standard tap features using the built-in SDK tests library."""

import datetime

from singer_sdk.testing import get_tap_test_class

from tap_xero.tap import TapXero

SAMPLE_CONFIG = {
    "client_id": "test_client_id",
    "client_secret": "test_client_secret",
    "refresh_token": "test_refresh_token",
    "tenant_id": "test_realm_id",
    "start_date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "user_agent": "tap-xero/3.0.0",
    "include_archived_contacts": False
}


# Run standard built-in tap tests from the SDK:
TestTapXero = get_tap_test_class(
    tap_class=TapXero,
    config=SAMPLE_CONFIG,
)
