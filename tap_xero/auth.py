"""OAuth2 authenticator for Xero API."""

import base64
import datetime
import ipaddress
import json
import sys
from functools import lru_cache
from urllib.parse import urlparse

import requests
from singer_sdk.authenticators import OAuthAuthenticator

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

ENDPOINT = "https://identity.xero.com/connect/token"


class NoRedirectOAuthAuthenticator(OAuthAuthenticator):
    """Refresh OAuth tokens without forwarding credentials through redirects."""

    @override
    def update_access_token(self) -> None:
        """Refresh a token with fail-closed redirects and bounded errors."""
        self.logger.info("Requesting new access token")
        request_time = datetime.datetime.now(datetime.timezone.utc)
        response = requests.post(
            self.auth_endpoint,
            headers=self._oauth_headers,
            data=self.oauth_request_payload,
            timeout=60,
            allow_redirects=False,
        )
        if 300 <= response.status_code < 400:
            raise RuntimeError("Failed to update access token (redirect rejected)")
        if not 200 <= response.status_code < 300:
            raise RuntimeError(f"Failed to update access token (status={response.status_code})")

        try:
            token_json = response.json()
            access_token = token_json["access_token"]
            expiration = token_json.get("expires_in", self._default_expiration)
            expires_in = int(expiration) if expiration else None
        except (KeyError, TypeError, ValueError):
            raise RuntimeError("Failed to update access token (invalid response)") from None
        if not isinstance(access_token, str) or not access_token:
            raise RuntimeError("Failed to update access token (invalid response)")

        self.access_token = access_token
        self.expires_in = expires_in
        self.last_refreshed = request_time


def validate_refresh_proxy_url(url: str) -> str:
    """Require encrypted transport, except for an explicit loopback proxy."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        parsed.port
    except (TypeError, ValueError) as exc:
        raise ValueError("refresh_proxy_url must be a valid URL") from exc

    if not hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError("refresh_proxy_url must not contain user information")

    is_loopback = hostname == "localhost"
    if not is_loopback:
        try:
            is_loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            pass

    if parsed.scheme != "https" and not (parsed.scheme == "http" and is_loopback):
        raise ValueError("refresh_proxy_url must use HTTPS unless it targets the local machine")
    return url


class XeroOAuth2Authenticator(NoRedirectOAuthAuthenticator):
    """Authenticator class for Xero OAuth2 flow."""

    @override
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> None:
        """Initialize the authenticator.

        Args:
            client_id: OAuth2 client ID.
            client_secret: OAuth2 client secret.
            refresh_token: OAuth2 refresh token.
            oauth_scopes: OAuth scopes.
        """
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            auth_endpoint=ENDPOINT,
        )
        self.refresh_token = refresh_token
        self._oauth_headers = self.oauth_request_headers

    @property
    def oauth_request_headers(self) -> dict[str, str]:
        """Return headers for OAuth token request.

        Uses Basic auth with base64 encoded client_id:client_secret.

        Returns:
            A dict with headers for the OAuth token request.
        """
        client_id = self.client_id
        client_secret = self.client_secret
        credentials = f"{client_id}:{client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()

        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    @override
    @property
    def oauth_request_body(self) -> dict:
        """Define the OAuth request body for the Xero API.

        Returns:
            A dict with the request body
        """
        return {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }


class ProxyXeroOAuth2Authenticator(NoRedirectOAuthAuthenticator):
    """Authenticator for Xero Proxy OAuth 2.0 flows."""

    @override
    def __init__(
        self,
        *,
        refresh_token: str,
        proxy_auth: str | None = None,
        auth_endpoint: str,
    ) -> None:
        """Initialize the proxy authenticator.

        Args:
            refresh_token: OAuth2 refresh token.
            proxy_auth: Authorization header value for proxy OAuth requests.
            kwargs: Additional keyword arguments for the authenticator.
        """
        super().__init__(auth_endpoint=validate_refresh_proxy_url(auth_endpoint))
        self.refresh_token = refresh_token
        self._proxy_auth = proxy_auth
        self._oauth_headers = self.oauth_request_headers

    @property
    def oauth_request_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}

        if self._proxy_auth:
            headers["Authorization"] = self._proxy_auth

        return headers

    @override
    @property
    def oauth_request_body(self) -> str:  # type: ignore[override]
        return json.dumps(
            {
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
        )


@lru_cache(maxsize=32)
def standard_authenticator(
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> XeroOAuth2Authenticator:
    """Share rotated tokens only between streams using the same credentials."""
    return XeroOAuth2Authenticator(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
    )


@lru_cache(maxsize=32)
def proxy_authenticator(
    refresh_token: str,
    proxy_auth: str | None,
    auth_endpoint: str,
) -> ProxyXeroOAuth2Authenticator:
    """Share a proxy token only between streams using the same proxy config."""
    return ProxyXeroOAuth2Authenticator(
        refresh_token=refresh_token,
        proxy_auth=proxy_auth,
        auth_endpoint=auth_endpoint,
    )
