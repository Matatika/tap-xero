"""Xero tap class."""

import sys

from singer_sdk import Stream, Tap
from singer_sdk import typing as th

from tap_xero import streams

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


class TapXero(Tap):
    """Singer tap for Xero."""

    name = "tap-xero"

    config_jsonschema = th.PropertiesList(
        th.Property(
            "client_id",
            th.StringType,
            required=True,
            description="OAuth2 client ID for Xero application",
        ),
        th.Property(
            "client_secret",
            th.StringType,
            required=True,
            secret=True,
            description="OAuth2 client secret for Xero application",
        ),
        th.Property(
            "tenant_id",
            th.StringType,
            required=True,
            description="Xero tenant/organisation ID",
        ),
        th.Property(
            "refresh_token",
            th.StringType,
            required=True,
            secret=True,
            description="OAuth2 refresh token (will be automatically updated during sync)",
        ),
        th.Property(
            "start_date",
            th.DateTimeType,
            required=True,
            description="Earliest record date to sync (ISO 8601 format)",
        ),
        th.Property(
            "user_agent",
            th.StringType,
            description="Custom User-Agent header for API requests",
        ),
        th.Property(
            "include_archived_contacts",
            th.BooleanType,
            default=False,
            description="Include archived contacts in the contacts stream",
        ),
    ).to_dict()

    @override
    def discover_streams(self) -> list[Stream]:
        """Return a list of discovered streams.

        Returns:
            List of stream instances
        """
        return [
            # Paginated Streams (10)
            streams.BankTransactionsStream(self),
            streams.ContactsStream(self),
            streams.QuotesStream(self),
            streams.CreditNotesStream(self),
            streams.InvoicesStream(self),
            streams.ManualJournalsStream(self),
            streams.OverpaymentsStream(self),
            streams.PaymentsStream(self),
            streams.PrepaymentsStream(self),
            streams.PurchaseOrdersStream(self),
            # Journal Stream (1)
            streams.JournalsStream(self),
            # Bookmarked Streams (7)
            streams.AccountsStream(self),
            streams.BankTransfersStream(self),
            streams.EmployeesStream(self),
            streams.ExpenseClaimsStream(self),
            streams.ItemsStream(self),
            streams.ReceiptsStream(self),
            streams.UsersStream(self),
            # Full Table Streams (8)
            streams.BrandingThemesStream(self),
            streams.ContactGroupsStream(self),
            streams.CurrenciesStream(self),
            streams.OrganisationsStream(self),
            streams.RepeatingInvoicesStream(self),
            streams.TaxRatesStream(self),
            streams.TrackingCategoriesStream(self),
            streams.LinkedTransactionsStream(self),
        ]


if __name__ == "__main__":
    TapXero.cli()
