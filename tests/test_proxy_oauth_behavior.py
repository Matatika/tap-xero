"""Behavioral tests for proxy OAuth authentication."""

import datetime
import json
from typing import Any

import pytest
import responses

from tap_xero.auth import ProxyXeroOAuth2Authenticator, XeroOAuth2Authenticator
from tap_xero.client import XeroStream
from tap_xero.tap import TapXero

# Proxy OAuth configuration (nested settings)
PROXY_CONFIG: dict[str, Any] = {
    "oauth_credentials": {
        "refresh_proxy_url": "http://localhost:8080/api/tokens/oauth2-xero/token",
        "refresh_proxy_url_auth": "Bearer proxy_test_token",
        "refresh_token": "test_refresh_token_1234",
    },
    "tenant_id": "test-tenant-id-proxy",
    "start_date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "user_agent": "tap-xero-test/3.1.0",
}

# Standard OAuth configuration (nested oauth_credentials)
STANDARD_CONFIG: dict[str, Any] = {
    "oauth_credentials": {
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "refresh_token": "test_refresh_token",
    },
    "tenant_id": "test-tenant-id-standard",
    "start_date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}


@responses.activate
def test_proxy_oauth_uses_correct_authenticator():
    """Test that proxy config uses ProxyXeroOAuth2Authenticator."""
    # Mock proxy endpoint
    responses.add(
        responses.POST,
        "http://localhost:8080/api/tokens/oauth2-xero/token",
        json={"access_token": "test_token", "expires_in": 1800},
        status=200,
    )

    tap = TapXero(config=PROXY_CONFIG)
    streams = tap.discover_streams()
    stream = streams[0]
    assert isinstance(stream, XeroStream)

    assert isinstance(
        stream.authenticator,
        ProxyXeroOAuth2Authenticator,
    ), f"Expected ProxyXeroOAuth2Authenticator, got {type(stream.authenticator).__name__}"


@responses.activate
def test_proxy_oauth_request_format():
    """Test that proxy OAuth makes correctly formatted HTTP requests."""
    # Mock proxy endpoint
    responses.add(
        responses.POST,
        "http://localhost:8080/api/tokens/oauth2-xero/token",
        json={"access_token": "proxy_access_token", "expires_in": 1800},
        status=200,
    )

    tap = TapXero(config=PROXY_CONFIG)
    streams = tap.discover_streams()
    stream = streams[0]
    assert isinstance(stream, XeroStream)

    # Trigger token refresh
    authenticator = stream.authenticator
    authenticator.update_access_token()

    # Verify request was made
    assert len(responses.calls) == 1

    request = responses.calls[0].request

    # Verify request
    assert request.url == "http://localhost:8080/api/tokens/oauth2-xero/token"
    assert request.headers["authorization"] == "Bearer proxy_test_token"
    assert request.headers["Content-Type"] == "application/json"
    assert request.body is not None

    body = json.loads(request.body)
    assert body["refresh_token"] == "test_refresh_token_1234"
    assert body["grant_type"] == "refresh_token"

    # Verify token was set
    assert authenticator.access_token == "proxy_access_token"


@responses.activate
def test_standard_oauth_uses_correct_authenticator():
    """Test that standard config uses XeroOAuth2Authenticator."""
    # Mock standard Xero endpoint
    responses.add(
        responses.POST,
        "https://identity.xero.com/connect/token",
        json={"access_token": "standard_token", "expires_in": 1800},
        status=200,
    )

    tap = TapXero(config=STANDARD_CONFIG)
    streams = tap.discover_streams()
    stream = streams[0]
    assert isinstance(stream, XeroStream)
    assert isinstance(stream.authenticator, XeroOAuth2Authenticator), (
        f"Expected XeroOAuth2Authenticator, got {type(stream.authenticator).__name__}"
    )


def test_invalid_oauth_config_raises_validation_error():
    """Test that incomplete OAuth configuration raises ConfigValidationError during schema validation."""
    from singer_sdk.exceptions import ConfigValidationError

    # Config with oauth_credentials but missing required fields for both modes
    invalid_config = {
        "oauth_credentials": {
            "refresh_token": "test_token",
            # Missing client_id + client_secret for standard OAuth
            # Missing refresh_proxy_url for proxy OAuth
        },
        "tenant_id": "test-tenant-id",
        "start_date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # Schema validation should fail during tap initialization
    with pytest.raises(ConfigValidationError):
        TapXero(config=invalid_config)
