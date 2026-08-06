"""Tests for shared Xero stream behaviour."""

import pytest

from tap_xero.streams import AccountsStream
from tap_xero.tap import TapXero

SAMPLE_CONFIG = {
    "oauth_credentials": {
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "refresh_token": "test_refresh_token",
    },
    "tenant_id": "test_tenant_id",
    "start_date": "2024-01-01T00:00:00Z",
}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("/Date(1419937200000+0000)/", "2014-12-30T11:00:00.000000Z"),
        ("/Date(-86400000+0000)/", "1969-12-31T00:00:00.000000Z"),
    ],
)
def test_parse_dotnet_date_preserves_the_timestamp(value: str, expected: str) -> None:
    """Convert .NET JSON timestamps before and after the Unix epoch."""
    stream = AccountsStream(TapXero(config=SAMPLE_CONFIG))

    assert stream.parse_dotnet_date(value) == expected
