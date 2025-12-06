"""OAuth2 authenticator for Xero API."""

import base64
from typing import Optional

import requests
from singer_sdk.authenticators import OAuthAuthenticator, SingletonMeta
from singer_sdk.streams import Stream as RESTStreamBase


class XeroOAuth2Authenticator(OAuthAuthenticator, metaclass=SingletonMeta):
    """Authenticator class for Xero OAuth2 flow."""

    @property
    def oauth_request_body(self) -> dict:
        """Define the OAuth request body for Xero.

        Returns:
            A dict with the request body for the OAuth token request.
        """
        return {
            "grant_type": "refresh_token",
            "refresh_token": self.config.get("refresh_token"),
        }

    @property
    def oauth_request_headers(self) -> dict:
        """Return headers for OAuth token request.

        Uses Basic auth with base64 encoded client_id:client_secret.

        Returns:
            A dict with headers for the OAuth token request.
        """
        client_id = self.config["client_id"]
        client_secret = self.config["client_secret"]
        credentials = f"{client_id}:{client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()

        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    @classmethod
    def create_for_stream(cls, stream: RESTStreamBase) -> "XeroOAuth2Authenticator":
        """Create an authenticator instance for a stream.

        Args:
            stream: The stream instance to create an authenticator for.

        Returns:
            A new authenticator instance.
        """
        return cls(
            stream=stream,
            auth_endpoint="https://identity.xero.com/connect/token",
            oauth_scopes="offline_access accounting.transactions accounting.contacts accounting.settings",
        )

    def update_access_token(self) -> None:
        """Update the access token and handle refresh token updates.

        Xero returns a new refresh token with each token refresh.
        We need to update the config and persist it.
        """
        headers = self.oauth_request_headers
        token_response = requests.post(
            self.auth_endpoint,
            headers=headers,
            data=self.oauth_request_body,
            timeout=60,
        )

        try:
            token_response.raise_for_status()
            self.logger.info("OAuth token refresh successful")
        except requests.HTTPError as ex:
            raise RuntimeError(
                f"Failed to refresh OAuth token: {token_response.status_code} "
                f"{token_response.text}"
            ) from ex

        token_json = token_response.json()
        self.access_token = token_json["access_token"]

        # Xero returns a new refresh token - update config
        new_refresh_token = token_json.get("refresh_token")
        if new_refresh_token:
            self.config["refresh_token"] = new_refresh_token
            self.logger.info("Refresh token updated")

            # Note: In a production scenario, you may want to persist this
            # to the config file. The SDK handles this automatically through
            # the config system, but be aware the refresh_token will change.
