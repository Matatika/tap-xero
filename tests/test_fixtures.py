"""Guards on the mocked Xero response fixtures."""

import datetime

from tap_xero.tap import TapXero
from tests.xero_fixtures import XERO_RESPONSES

CONFIG = {
    "oauth_credentials": {
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "refresh_token": "test_refresh_token",
    },
    "tenant_id": "test-tenant-id-fixtures",
    "start_date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}


def test_every_stream_has_fixture_records() -> None:
    """A stream without fixture records makes every record-dependent test vacuous."""
    endpoints = {stream.path.lstrip("/") for stream in TapXero(config=CONFIG).streams.values()}
    missing = sorted(endpoints - XERO_RESPONSES.keys())

    assert not missing, f"Streams without fixture records: {missing}"


def test_fixture_records_are_non_empty() -> None:
    """An empty fixture list is the same vacuous-pass problem in a different shape."""
    empty = sorted(endpoint for endpoint, records in XERO_RESPONSES.items() if not records)

    assert not empty, f"Endpoints with no fixture records: {empty}"
