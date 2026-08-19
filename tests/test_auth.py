"""Behavioral tests for authentication."""

import copy
import datetime
import json
from typing import Any

import pytest
import responses

from tap_xero.auth import (
    ENDPOINT,
    ProxyXeroOAuth2Authenticator,
    XeroOAuth2Authenticator,
    proxy_authenticator,
    standard_authenticator,
    validate_refresh_proxy_url,
)
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


@pytest.mark.parametrize("mode", ["standard", "proxy"])
@responses.activate
def test_oauth_refresh_rejects_cross_origin_redirects_without_forwarding_secrets(mode):
    evil_url = "https://evil.example/token"
    if mode == "standard":
        authenticator = XeroOAuth2Authenticator(
            client_id="redirect-client",
            client_secret="redirect-secret",
            refresh_token="redirect-refresh-token",
        )
        endpoint = ENDPOINT
    else:
        authenticator = ProxyXeroOAuth2Authenticator(
            refresh_token="redirect-refresh-token",
            proxy_auth="Bearer redirect-proxy-secret",
            auth_endpoint="https://proxy.example/token",
        )
        endpoint = "https://proxy.example/token"

    responses.add(responses.POST, endpoint, status=302, headers={"Location": evil_url})
    responses.add(responses.POST, evil_url, json={"access_token": "should-not-run"})

    with pytest.raises(RuntimeError, match="redirect rejected"):
        authenticator.update_access_token()

    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == endpoint
    assert all(call.request.url != evil_url for call in responses.calls)


@pytest.mark.parametrize("mode", ["standard", "proxy"])
@responses.activate
def test_oauth_refresh_errors_do_not_echo_response_or_credentials(mode):
    if mode == "standard":
        authenticator = XeroOAuth2Authenticator(
            client_id="error-client",
            client_secret="error-secret",
            refresh_token="error-refresh-token",
        )
        endpoint = ENDPOINT
    else:
        authenticator = ProxyXeroOAuth2Authenticator(
            refresh_token="error-refresh-token",
            proxy_auth="Bearer error-proxy-secret",
            auth_endpoint="https://proxy.example/token",
        )
        endpoint = "https://proxy.example/token"

    responses.add(
        responses.POST,
        endpoint,
        body="Authorization: Bearer reflected-secret\r\nerror-refresh-token",
        status=400,
    )

    with pytest.raises(RuntimeError) as raised:
        authenticator.update_access_token()

    message = str(raised.value)
    assert message == "Failed to update access token (status=400)"
    assert "reflected-secret" not in message
    assert "error-refresh-token" not in message
    assert "error-secret" not in message
    assert "error-proxy-secret" not in message


@pytest.mark.parametrize("mode", ["standard", "proxy"])
@pytest.mark.parametrize(
    "token_response",
    [
        pytest.param({"body": "<html>invalid-body-secret</html>"}, id="non-json-body"),
        pytest.param({"json": ["access_token", "invalid-body-secret"]}, id="json-array-body"),
        pytest.param({"json": {"expires_in": 1800}}, id="missing-access-token"),
        pytest.param({"json": {"access_token": "", "expires_in": 1800}}, id="empty-access-token"),
        pytest.param({"json": {"access_token": 12345}}, id="non-string-access-token"),
        pytest.param(
            {"json": {"access_token": "ok", "expires_in": "soon"}}, id="expires-not-a-number"
        ),
        pytest.param(
            {"json": {"access_token": "ok", "expires_in": {"seconds": 60}}},
            id="expires-not-a-scalar",
        ),
    ],
)
@responses.activate
def test_oauth_refresh_rejects_malformed_token_responses(mode, token_response):
    """A 200 response the tap cannot read must fail closed, without echoing it."""
    if mode == "standard":
        authenticator = XeroOAuth2Authenticator(
            client_id="invalid-client",
            client_secret="invalid-secret",
            refresh_token="invalid-refresh-token",
        )
        endpoint = ENDPOINT
    else:
        authenticator = ProxyXeroOAuth2Authenticator(
            refresh_token="invalid-refresh-token",
            proxy_auth="Bearer invalid-proxy-secret",
            auth_endpoint="https://proxy.example/token",
        )
        endpoint = "https://proxy.example/token"

    responses.add(responses.POST, endpoint, status=200, **token_response)

    with pytest.raises(RuntimeError) as raised:
        authenticator.update_access_token()

    assert str(raised.value) == "Failed to update access token (invalid response)"

    # No half-applied state: a rejected response must not leave a token behind.
    assert authenticator.access_token is None
    assert authenticator.refresh_token == "invalid-refresh-token"


@pytest.mark.parametrize("mode", ["standard", "proxy"])
@pytest.mark.parametrize("rotates", [True, False])
@responses.activate
def test_oauth_refresh_preserves_rotation_and_reuses_the_current_token(mode, rotates):
    initial_token = "initial-refresh-token"
    rotated_token = "rotated-refresh-token"
    if mode == "standard":
        authenticator = XeroOAuth2Authenticator(
            client_id="rotation-client",
            client_secret="rotation-secret",
            refresh_token=initial_token,
        )
        endpoint = ENDPOINT
    else:
        authenticator = ProxyXeroOAuth2Authenticator(
            refresh_token=initial_token,
            proxy_auth="Bearer rotation-proxy-secret",
            auth_endpoint="https://proxy.example/token",
        )
        endpoint = "https://proxy.example/token"

    first_response = {"access_token": "access-one", "expires_in": 1800}
    if rotates:
        first_response["refresh_token"] = rotated_token
    responses.add(responses.POST, endpoint, json=first_response)
    responses.add(
        responses.POST,
        endpoint,
        json={"access_token": "access-two", "expires_in": 1800},
    )

    authenticator.update_access_token()
    authenticator.update_access_token()

    expected_token = rotated_token if rotates else initial_token
    assert authenticator.refresh_token == expected_token
    second_body = responses.calls[1].request.body
    if mode == "proxy":
        assert json.loads(second_body)["refresh_token"] == expected_token
    else:
        assert f"refresh_token={expected_token}" in second_body


def test_authenticators_do_not_share_credentials_between_configurations():
    first = standard_authenticator("first-client", "first-secret", "first-token")
    first_again = standard_authenticator("first-client", "first-secret", "first-token")
    second = standard_authenticator("second-client", "second-secret", "second-token")

    assert first is first_again
    assert first is not second
    assert first.client_id == "first-client"
    assert first.refresh_token == "first-token"
    assert second.client_id == "second-client"
    assert second.refresh_token == "second-token"


@pytest.mark.parametrize(
    ("refresh_token", "proxy_auth", "auth_endpoint"),
    [
        pytest.param("other-token", "Bearer proxy-a", "https://proxy-a.example/token", id="token"),
        pytest.param("proxy-token", "Bearer proxy-b", "https://proxy-a.example/token", id="auth"),
        pytest.param(
            "proxy-token", "Bearer proxy-a", "https://proxy-b.example/token", id="endpoint"
        ),
    ],
)
def test_proxy_authenticators_do_not_share_credentials_between_configurations(
    refresh_token,
    proxy_auth,
    auth_endpoint,
):
    """Every part of the proxy cache key must isolate, the endpoint included.

    Two different proxy endpoints sharing one authenticator would also share the
    refresh token it rotates in place.
    """
    first = proxy_authenticator("proxy-token", "Bearer proxy-a", "https://proxy-a.example/token")
    first_again = proxy_authenticator(
        "proxy-token",
        "Bearer proxy-a",
        "https://proxy-a.example/token",
    )
    other = proxy_authenticator(refresh_token, proxy_auth, auth_endpoint)

    assert first is first_again
    assert first is not other
    assert other.refresh_token == refresh_token
    assert other.auth_endpoint == auth_endpoint
    assert other.oauth_request_headers["Authorization"] == proxy_auth

    # A rotated token on one proxy configuration must not reach the other.
    first.refresh_token = "rotated-proxy-token"
    assert other.refresh_token == refresh_token


@responses.activate
def test_streams_using_different_proxies_get_separate_authenticators():
    """The proxy authenticator is reached through the stream, not just the cache."""
    responses.add(
        responses.POST,
        "http://localhost:8080/api/tokens/oauth2-xero/token",
        json={"access_token": "token_a", "expires_in": 1800},
        status=200,
    )

    other_config = copy.deepcopy(PROXY_CONFIG)
    other_config["oauth_credentials"]["refresh_proxy_url"] = "https://proxy.example/token"

    stream = TapXero(config=PROXY_CONFIG).discover_streams()[0]
    other_stream = TapXero(config=other_config).discover_streams()[0]
    assert isinstance(stream, XeroStream)
    assert isinstance(other_stream, XeroStream)

    authenticator = stream.authenticator
    other_authenticator = other_stream.authenticator

    assert isinstance(authenticator, ProxyXeroOAuth2Authenticator)
    assert isinstance(other_authenticator, ProxyXeroOAuth2Authenticator)
    assert authenticator is not other_authenticator
    assert authenticator.auth_endpoint == "http://localhost:8080/api/tokens/oauth2-xero/token"
    assert other_authenticator.auth_endpoint == "https://proxy.example/token"

    # Only the first proxy is mocked, so a shared authenticator would be visible here.
    authenticator.update_access_token()
    assert authenticator.access_token == "token_a"
    assert other_authenticator.access_token is None


def test_refresh_proxy_requires_https_except_for_loopback():
    assert validate_refresh_proxy_url("https://proxy.example.com/token") == (
        "https://proxy.example.com/token"
    )
    assert validate_refresh_proxy_url("http://localhost:8080/token") == (
        "http://localhost:8080/token"
    )
    assert validate_refresh_proxy_url("http://127.0.0.1:8080/token") == (
        "http://127.0.0.1:8080/token"
    )

    for url in (
        "http://proxy.example.com/token",
        "ftp://proxy.example.com/token",
        "https://user@proxy.example.com/token",
        "https://proxy.example.com:not-a-port/token",
        "https://[malformed",
    ):
        with pytest.raises(ValueError):
            validate_refresh_proxy_url(url)


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
