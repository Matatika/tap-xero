"""Tests for Xero stream behaviour."""

from tap_xero.streams import JournalsStream
from tap_xero.tap import TapXero

CONFIG = {
    "oauth_credentials": {
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "refresh_token": "test-refresh-token",
    },
    "tenant_id": "test-tenant-id",
    "start_date": "2020-01-01T00:00:00Z",
}


def get_journals_stream() -> JournalsStream:
    """Create a Journals stream with a valid tap configuration."""
    return JournalsStream(TapXero(config=CONFIG))


def test_journals_omits_offset_for_a_fresh_sync():
    """A start date is not a valid JournalNumber offset."""
    stream = get_journals_stream()

    stream._write_starting_replication_value(None)

    assert stream.get_url_params(None, None) == {}


def test_journals_uses_a_saved_journal_number_as_offset():
    """A numeric JournalNumber bookmark is sent as the Xero offset."""
    stream = get_journals_stream()
    stream.stream_state.update(
        {"replication_key": "JournalNumber", "replication_key_value": 37},
    )

    stream._write_starting_replication_value(None)

    assert stream.get_url_params(None, None) == {"offset": 37}


def test_journals_uses_the_page_token_as_offset():
    """Pagination continues from the most recent journal number."""
    stream = get_journals_stream()

    assert stream.get_url_params(None, 38) == {"offset": 38}
