"""Tests for stream pagination."""

from unittest.mock import Mock

import pytest

from tap_xero.streams import InvoicesStream
from tap_xero.tap import TapXero

SAMPLE_CONFIG = {
    "oauth_credentials": {
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "refresh_token": "test_refresh_token",
    },
    "tenant_id": "test_realm_id",
    "start_date": "2024-01-01T00:00:00Z",
}


@pytest.mark.parametrize(
    ("record_count", "previous_token", "expected_token"),
    [
        (100, None, 2),
        (100, 2, 3),
        (99, None, None),
    ],
)
def test_paginated_stream_advances_after_a_full_page(
    record_count: int,
    previous_token: int | None,
    expected_token: int | None,
) -> None:
    """Paginated streams continue only when the response fills a page."""
    stream = InvoicesStream(TapXero(config=SAMPLE_CONFIG))
    response = Mock()
    response.json.return_value = {"Invoices": [{}] * record_count}

    assert stream.get_next_page_token(response, previous_token) == expected_token
