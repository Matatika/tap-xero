"""OAuth2 authenticator for Xero API."""

import base64
import sys

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
