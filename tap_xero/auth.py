"""OAuth2 authenticator for Xero API."""

import base64
import json
import sys

from singer_sdk.authenticators import OAuthAuthenticator, SingletonMeta

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

ENDPOINT = "https://identity.xero.com/connect/token"


class XeroOAuth2Authenticator(OAuthAuthenticator, metaclass=SingletonMeta):
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


class ProxyXeroOAuth2Authenticator(OAuthAuthenticator, metaclass=SingletonMeta):
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
        super().__init__(auth_endpoint=auth_endpoint)
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
