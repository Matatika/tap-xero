"""REST client for Xero API."""

from __future__ import annotations

import re
import sys
from collections.abc import Generator
from datetime import datetime, timezone
from functools import cached_property
from typing import TYPE_CHECKING, Any

import backoff
from singer_sdk.exceptions import RetriableAPIError
from singer_sdk.streams import RESTStream

from tap_xero.auth import ProxyXeroOAuth2Authenticator, XeroOAuth2Authenticator

if TYPE_CHECKING:
    from collections.abc import Generator

    import requests
    from singer_sdk.helpers.types import Auth, Context, Record

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


class XeroAPIError(Exception):
    """Base exception for Xero API errors."""

    @override
    def __init__(self, message: str, response: requests.Response | None = None):
        """Initialize exception."""
        super().__init__(message)
        self.response = response


class XeroRateLimitError(RetriableAPIError):
    """Exception for Xero rate limit errors (429)."""


class XeroStream(RESTStream):
    """Base stream class for Xero API."""

    url_base = "https://api.xero.com/api.xro/2.0"

    # Xero uses .NET JSON date format: /Date(1419937200000+0000)/
    _dotnet_date_pattern = re.compile(r"\/Date\((-?\d+)([\+\-]\d{4})?\)\/")

    @override
    @cached_property
    def authenticator(self) -> Auth:
        """Return a new authenticator object.

        Determines whether to use standard OAuth or proxy OAuth based on
        the oauth_credentials configuration.

        Returns:
            An authenticator instance (either standard or proxy).
        """
        oauth_credentials = self.config["oauth_credentials"]

        # Check for standard OAuth credentials (client_id + client_secret)
        client_id = oauth_credentials.get("client_id")
        client_secret = oauth_credentials.get("client_secret")

        if client_id and client_secret:
            # Standard OAuth mode
            return XeroOAuth2Authenticator(
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=oauth_credentials["refresh_token"],
                auth_endpoint="https://identity.xero.com/connect/token",
                oauth_scopes="offline_access accounting.transactions accounting.contacts accounting.settings",
            )

        # Check for proxy OAuth credentials (refresh_proxy_url)
        refresh_proxy_url = oauth_credentials.get("refresh_proxy_url")

        if refresh_proxy_url:
            # Proxy OAuth mode
            auth_headers = {
                "authorization": oauth_credentials.get("refresh_proxy_url_auth", ""),
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            auth_body = {
                "refresh_token": oauth_credentials["refresh_token"],
                "grant_type": "refresh_token",
            }
            return ProxyXeroOAuth2Authenticator(
                auth_endpoint=refresh_proxy_url,
                oauth_scopes="offline_access accounting.transactions accounting.contacts accounting.settings",
                auth_headers=auth_headers,
                auth_body=auth_body,
            )

        # If neither mode is configured, raise error
        msg = (
            "OAuth configuration invalid. Provide either:\n"
            "  1. oauth_credentials with client_id, client_secret, and refresh_token (standard OAuth), or\n"
            "  2. oauth_credentials with refresh_proxy_url and refresh_token (proxy OAuth)"
        )
        raise ValueError(msg)

    @override
    @property
    def http_headers(self) -> dict[str, str]:
        """Return headers for HTTP requests.

        Returns:
            Dictionary of HTTP headers.
        """
        headers = super().http_headers
        headers["Xero-Tenant-Id"] = self.config["tenant_id"]
        headers["Accept"] = "application/json"

        if user_agent := self.config.get("user_agent"):
            headers["User-Agent"] = user_agent

        if starting_timestamp := self.get_starting_replication_key_value(self.context):
            # Xero uses If-Modified-Since header to fetch only the changes since the last bookmark
            headers["If-Modified-Since"] = starting_timestamp

        return headers

    def parse_dotnet_date(self, date_str: str) -> str | None:
        """Parse .NET JSON date format to RFC3339.

        Xero returns dates in .NET format: /Date(1419937200000+0000)/
        This converts to RFC3339: 2014-12-30T09:00:00.000000Z

        Args:
            date_str: Date string in .NET JSON format

        Returns:
            RFC3339 formatted date string or None
        """
        if not date_str or not isinstance(date_str, str):
            return None

        # Try .NET JSON date format
        if match := self._dotnet_date_pattern.match(date_str):
            timestamp_ms = int(match.group(1))
            # Convert milliseconds to seconds
            timestamp = timestamp_ms / 1000.0

            # Handle negative timestamps (dates before epoch)
            if timestamp < 0:
                timestamp = 0

            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # If already in ISO format, return as is
        return date_str if "T" in date_str else None

    def transform_dotnet_dates(self, record: Record) -> Record:
        """Recursively transform all .NET dates in a record to RFC3339.

        Args:
            record: Dictionary record from API

        Returns:
            Record with transformed dates
        """
        if not isinstance(record, dict):
            return record

        transformed: Record = {}
        for key, value in record.items():
            if isinstance(value, str) and "/Date(" in value:
                transformed[key] = self.parse_dotnet_date(value)
            elif isinstance(value, dict):
                transformed[key] = self.transform_dotnet_dates(value)
            elif isinstance(value, list):
                transformed[key] = [
                    self.transform_dotnet_dates(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                transformed[key] = value

        return transformed

    @override
    def backoff_wait_generator(self) -> Generator[int | float, Any, None]:
        """Return backoff wait generator with custom logic for rate limits.

        Returns:
            Backoff wait generator function
        """
        return backoff.expo(base=2, factor=2, max_value=60)

    @override
    def backoff_max_tries(self) -> int:
        """Return max retry attempts.

        Returns:
            Maximum number of retry attempts
        """
        return 5

    @override
    def validate_response(self, response: requests.Response) -> None:
        """Validate HTTP response and raise appropriate exceptions.

        Args:
            response: HTTP response object

        Raises:
            XeroRateLimitError: For 429 rate limit errors
            XeroAPIError: For other API errors
        """
        if response.status_code == 429:
            # If Retry-After is present, it's usually the per-minute limit
            if retry_after := response.headers.get("Retry-After"):
                self.logger.warning(f"Rate limit hit, will retry after {retry_after} seconds")
                error_msg = f"Rate limit exceeded (429). Retry-After: {retry_after}"
                raise XeroRateLimitError(error_msg, response=response)
            # Daily limit - don't retry
            raise XeroAPIError("Daily API rate limit exceeded. Cannot retry.", response)

        if response.status_code == 503:
            raise RetriableAPIError("Service unavailable (503). Will retry.", response=response)

        if response.status_code >= 500:
            raise RetriableAPIError(
                f"Server error ({response.status_code}). Will retry.",
                response=response,
            )

        if response.status_code == 401:
            # OAuth token might need refresh
            raise RetriableAPIError(
                "Unauthorized (401). Token may need refresh.",
                response=response,
            )

        if response.status_code >= 400:
            error_msg = f"Client error {response.status_code}"
            try:
                error_data = response.json()
                if "Message" in error_data:
                    error_msg += f": {error_data['Message']}"
            except Exception:
                error_msg += f": {response.text}"

            raise XeroAPIError(error_msg, response)

    @override
    def post_process(self, row: Record, context: Context | None = None) -> Record | None:
        """Post-process each record, transforming dates.

        Args:
            row: Individual record from the API
            context: Stream partition or context dictionary

        Returns:
            Transformed record
        """
        # Transform .NET dates to RFC3339
        return self.transform_dotnet_dates(row)
