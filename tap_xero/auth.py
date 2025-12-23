"""OAuth2 authenticator for Xero API."""

import base64
import json
import sys
from typing import Any

import requests
from singer_sdk.authenticators import OAuthAuthenticator, SingletonMeta

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


class XeroOAuth2Authenticator(OAuthAuthenticator, metaclass=SingletonMeta):
    """Authenticator class for Xero OAuth2 flow."""

    @override
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        auth_endpoint: str,
        oauth_scopes: str,
    ) -> None:
        """Initialize the authenticator.

        Args:
            client_id: OAuth2 client ID.
            client_secret: OAuth2 client secret.
            refresh_token: OAuth2 refresh token.
            auth_endpoint: OAuth2 token endpoint URL.
            oauth_scopes: OAuth scopes.
        """
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            auth_endpoint=auth_endpoint,
            oauth_scopes=oauth_scopes,
        )
        self._oauth_headers = self.oauth_request_headers
        self._refresh_token = refresh_token

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
        """Define the OAuth request body for the QuickBooks API.

        Returns:
            A dict with the request body
        """
        return {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }


class ProxyXeroOAuth2Authenticator(OAuthAuthenticator, metaclass=SingletonMeta):
    """Authenticator for Xero Proxy OAuth 2.0 flows.

    This authenticator supports OAuth refresh through a proxy endpoint instead of
    directly communicating with Xero's OAuth server. The proxy endpoint handles
    the actual OAuth token refresh and returns the access token.
    """

    @override
    def __init__(
        self,
        auth_endpoint: str,
        oauth_scopes: str,
        auth_headers: dict[str, str],
        auth_body: dict[str, Any],
    ) -> None:
        """Initialize the proxy authenticator.

        Args:
            auth_endpoint: The proxy OAuth token endpoint URL.
            oauth_scopes: OAuth scopes for the Xero API.
            auth_headers: Custom headers for the proxy OAuth request.
            auth_body: Custom body for the proxy OAuth request.
        """
        super().__init__(
            auth_endpoint=auth_endpoint,
            oauth_scopes=oauth_scopes,
        )
        self._auth_headers = auth_headers
        self._auth_body = auth_body

    @override
    def update_access_token(self) -> None:
        """Update access token via proxy endpoint.

        Makes a POST request to the proxy endpoint with custom headers and JSON body.
        The proxy handles the actual OAuth flow with Xero.

        Raises:
            RuntimeError: When proxy OAuth login fails.
        """
        from singer_sdk.helpers._util import utc_now

        request_time = utc_now()

        token_response = requests.post(
            self.auth_endpoint,
            headers=self._auth_headers,
            data=json.dumps(self._auth_body),
        )

        try:
            token_response.raise_for_status()
            self.logger.info("Proxy OAuth authorization attempt was successful.")
        except Exception as ex:
            raise RuntimeError(
                f"Failed proxy OAuth login, response was '{token_response.json()}'. {ex}"
            ) from ex

        token_json = token_response.json()
        self.access_token = token_json["access_token"]
        self.expires_in = token_json.get("expires_in", 3600)  # Default 1 hour
        self.last_refreshed = request_time

    @override
    @property
    def oauth_request_body(self) -> dict:
        """Define the OAuth request body.

        Returns:
            Empty dict as body is handled by update_access_token.
        """
        return {}
