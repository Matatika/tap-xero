"""Stream classes for tap-xero."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from singer_sdk import typing as th

from tap_xero.client import XeroStream

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

if TYPE_CHECKING:
    import requests
    from singer_sdk.helpers.types import Context


class PaginatedStream(XeroStream):
    """Base class for paginated Xero streams with incremental sync support."""

    replication_key = "UpdatedDateUTC"
    page_size = 100

    # Xero pagination uses 1-based page numbers
    @override
    def get_url_params(
        self,
        context: Context | None,
        next_page_token: Any | None,
    ) -> dict[str, Any]:
        """Get URL query parameters.

        Args:
            context: Stream partition or context dictionary
            next_page_token: Token for pagination

        Returns:
            Dictionary of query parameters
        """
        params: dict[str, Any] = {}

        # Add pagination
        if next_page_token:
            params["page"] = next_page_token
        else:
            params["page"] = 1

        # Add replication key filter for incremental sync
        # starting_timestamp = self.get_starting_replication_key_value(context)
        # if starting_timestamp:
        #    # Xero uses If-Modified-Since header or where clause
        #    params["where"] = f'{self.replication_key}>DateTime({starting_timestamp.replace(":", "%3A")})'

        # Order by replication key (some streams don't support this due to Xero bugs)
        # if self.supports_order_by:
        #    params["order"] = f"{self.replication_key} ASC"

        return params

    @property
    def supports_order_by(self) -> bool:
        """Whether this stream supports ORDER BY parameter.

        Some Xero streams have bugs with ordering.

        Returns:
            True if ordering is supported
        """
        return True

    def get_next_page_token(self, response: Any, previous_token: Any | None) -> Any | None:
        """Get next page token.

        Args:
            response: HTTP response
            previous_token: Previous page token

        Returns:
            Next page token or None if no more pages
        """
        data = response.json()

        # Get the records from the response
        records = data.get(self.records_jsonpath.split(".")[0], [])

        # If we got a full page, there might be more
        if len(records) >= self.page_size:
            current_page = previous_token or 1
            return current_page + 1

        return None


class FullTableStream(XeroStream):
    """Base class for streams that don't support incremental sync."""

    replication_key = None


# Paginated Streams (10)


class BankTransactionsStream(PaginatedStream):
    """Bank Transactions stream."""

    name = "bank_transactions"
    path = "/BankTransactions"
    primary_keys = ["BankTransactionID"]
    replication_key = "UpdatedDateUTC"
    records_jsonpath = "$.BankTransactions[*]"

    schema = th.PropertiesList(
        th.Property("BankTransactionID", th.StringType),
        th.Property("Type", th.StringType),
        th.Property("Contact", th.ObjectType()),
        th.Property("LineItems", th.ArrayType(th.ObjectType())),
        th.Property("BankAccount", th.ObjectType()),
        th.Property("IsReconciled", th.BooleanType),
        th.Property("Date", th.StringType),
        th.Property("Reference", th.StringType),
        th.Property("CurrencyCode", th.StringType),
        th.Property("CurrencyRate", th.NumberType),
        th.Property("Status", th.StringType),
        th.Property("LineAmountTypes", th.StringType),
        th.Property("SubTotal", th.NumberType),
        th.Property("TotalTax", th.NumberType),
        th.Property("Total", th.NumberType),
        th.Property("UpdatedDateUTC", th.StringType),
        th.Property("HasAttachments", th.BooleanType),
        th.Property("DateString", th.StringType),
    ).to_dict()


class ContactsStream(PaginatedStream):
    """Contacts stream."""

    name = "contacts"
    path = "/Contacts"
    primary_keys = ["ContactID"]
    replication_key = "UpdatedDateUTC"
    records_jsonpath = "$.Contacts[*]"

    schema = th.PropertiesList(
        th.Property("ContactID", th.StringType),
        th.Property("ContactNumber", th.StringType),
        th.Property("AccountNumber", th.StringType),
        th.Property("ContactStatus", th.StringType),
        th.Property("Name", th.StringType),
        th.Property("FirstName", th.StringType),
        th.Property("LastName", th.StringType),
        th.Property("EmailAddress", th.StringType),
        th.Property("BankAccountDetails", th.StringType),
        th.Property("TaxNumber", th.StringType),
        th.Property("AccountsReceivableTaxType", th.StringType),
        th.Property("AccountsPayableTaxType", th.StringType),
        th.Property("Addresses", th.ArrayType(th.ObjectType())),
        th.Property("Phones", th.ArrayType(th.ObjectType())),
        th.Property("UpdatedDateUTC", th.StringType),
        th.Property("ContactGroups", th.ArrayType(th.ObjectType())),
        th.Property("IsSupplier", th.BooleanType),
        th.Property("IsCustomer", th.BooleanType),
        th.Property("DefaultCurrency", th.StringType),
        th.Property("HasAttachments", th.BooleanType),
        th.Property("BrandingTheme", th.ObjectType()),
        th.Property("Balances", th.ObjectType()),
        th.Property("ContactPersons", th.ArrayType(th.ObjectType())),
        th.Property("HasValidationErrors", th.BooleanType),
        th.Property("BatchPayments", th.ObjectType()),
    ).to_dict()

    @override
    def get_url_params(
        self,
        context: Context | None,
        next_page_token: Any | None,
    ) -> dict[str, Any]:
        """Get URL query parameters including archived contacts if configured.

        Args:
            context: Stream partition or context dictionary
            next_page_token: Token for pagination

        Returns:
            Dictionary of query parameters
        """
        params = super().get_url_params(context, next_page_token)

        # Add includeArchived parameter if configured
        if self.config.get("include_archived_contacts"):
            params["includeArchived"] = "true"

        return params


class QuotesStream(PaginatedStream):
    """Quotes stream."""

    name = "quotes"
    path = "/Quotes"
    primary_keys = ["QuoteID"]
    replication_key = "UpdatedDateUTC"
    records_jsonpath = "$.Quotes[*]"

    schema = th.PropertiesList(
        th.Property("QuoteID", th.StringType),
        th.Property("QuoteNumber", th.StringType),
        th.Property("Reference", th.StringType),
        th.Property("Terms", th.StringType),
        th.Property("Contact", th.ObjectType()),
        th.Property("LineItems", th.ArrayType(th.ObjectType())),
        th.Property("Date", th.StringType),
        th.Property("DateString", th.StringType),
        th.Property("ExpiryDate", th.StringType),
        th.Property("ExpiryDateString", th.StringType),
        th.Property("Status", th.StringType),
        th.Property("CurrencyCode", th.StringType),
        th.Property("CurrencyRate", th.NumberType),
        th.Property("SubTotal", th.NumberType),
        th.Property("TotalTax", th.NumberType),
        th.Property("Total", th.NumberType),
        th.Property("TotalDiscount", th.NumberType),
        th.Property("Title", th.StringType),
        th.Property("Summary", th.StringType),
        th.Property("BrandingThemeID", th.StringType),
        th.Property("UpdatedDateUTC", th.StringType),
        th.Property("LineAmountTypes", th.StringType),
    ).to_dict()


class CreditNotesStream(PaginatedStream):
    """Credit Notes stream."""

    name = "credit_notes"
    path = "/CreditNotes"
    primary_keys = ["CreditNoteID"]
    replication_key = "UpdatedDateUTC"
    records_jsonpath = "$.CreditNotes[*]"

    schema = th.PropertiesList(
        th.Property("CreditNoteID", th.StringType),
        th.Property("CreditNoteNumber", th.StringType),
        th.Property("Type", th.StringType),
        th.Property("Contact", th.ObjectType()),
        th.Property("Date", th.StringType),
        th.Property("DueDate", th.StringType),
        th.Property("Status", th.StringType),
        th.Property("LineAmountTypes", th.StringType),
        th.Property("LineItems", th.ArrayType(th.ObjectType())),
        th.Property("SubTotal", th.NumberType),
        th.Property("TotalTax", th.NumberType),
        th.Property("Total", th.NumberType),
        th.Property("UpdatedDateUTC", th.StringType),
        th.Property("CurrencyCode", th.StringType),
        th.Property("FullyPaidOnDate", th.StringType),
        th.Property("RemainingCredit", th.NumberType),
        th.Property("Allocations", th.ArrayType(th.ObjectType())),
        th.Property("HasAttachments", th.BooleanType),
        th.Property("Payments", th.ArrayType(th.ObjectType())),
        th.Property("ID", th.StringType),
        th.Property("HasErrors", th.BooleanType),
        th.Property("InvoiceAddresses", th.ArrayType(th.ObjectType())),
        th.Property("Reference", th.StringType),
        th.Property("DateString", th.StringType),
    ).to_dict()


class InvoicesStream(PaginatedStream):
    """Invoices stream."""

    name = "invoices"
    path = "/Invoices"
    primary_keys = ["InvoiceID"]
    replication_key = "UpdatedDateUTC"
    records_jsonpath = "$.Invoices[*]"

    schema = th.PropertiesList(
        th.Property("InvoiceID", th.StringType),
        th.Property("Type", th.StringType),
        th.Property("InvoiceNumber", th.StringType),
        th.Property("Reference", th.StringType),
        th.Property("Payments", th.ArrayType(th.ObjectType())),
        th.Property("CreditNotes", th.ArrayType(th.ObjectType())),
        th.Property("Prepayments", th.ArrayType(th.ObjectType())),
        th.Property("Overpayments", th.ArrayType(th.ObjectType())),
        th.Property("AmountDue", th.NumberType),
        th.Property("AmountPaid", th.NumberType),
        th.Property("AmountCredited", th.NumberType),
        th.Property("CurrencyRate", th.NumberType),
        th.Property("IsDiscounted", th.BooleanType),
        th.Property("HasAttachments", th.BooleanType),
        th.Property("Contact", th.ObjectType()),
        th.Property("DateString", th.StringType),
        th.Property("Date", th.StringType),
        th.Property("DueDateString", th.StringType),
        th.Property("DueDate", th.StringType),
        th.Property("Status", th.StringType),
        th.Property("LineAmountTypes", th.StringType),
        th.Property("LineItems", th.ArrayType(th.ObjectType())),
        th.Property("SubTotal", th.NumberType),
        th.Property("TotalTax", th.NumberType),
        th.Property("Total", th.NumberType),
        th.Property("TotalDiscount", th.NumberType),
        th.Property("UpdatedDateUTC", th.StringType),
        th.Property("CurrencyCode", th.StringType),
        th.Property("FullyPaidOnDate", th.StringType),
        th.Property("BrandingThemeID", th.StringType),
        th.Property("SentToContact", th.BooleanType),
        th.Property("Url", th.StringType),
        th.Property("InvoiceAddresses", th.ArrayType(th.ObjectType())),
        th.Property("HasErrors", th.BooleanType),
        th.Property("InvoicePaymentServices", th.ArrayType(th.ObjectType())),
        th.Property("RepeatingInvoiceID", th.StringType),
    ).to_dict()


class ManualJournalsStream(PaginatedStream):
    """Manual Journals stream."""

    name = "manual_journals"
    path = "/ManualJournals"
    primary_keys = ["ManualJournalID"]
    replication_key = "UpdatedDateUTC"
    records_jsonpath = "$.ManualJournals[*]"

    schema = th.PropertiesList(
        th.Property("ManualJournalID", th.StringType),
        th.Property("Narration", th.StringType),
        th.Property("JournalLines", th.ArrayType(th.ObjectType())),
        th.Property("Date", th.StringType),
        th.Property("DateString", th.StringType),
        th.Property("Status", th.StringType),
        th.Property("LineAmountTypes", th.StringType),
        th.Property("UpdatedDateUTC", th.StringType),
        th.Property("ShowOnCashBasisReports", th.BooleanType),
        th.Property("HasAttachments", th.BooleanType),
    ).to_dict()

    @property
    def supports_order_by(self) -> bool:
        """Manual journals don't support ORDER BY due to Xero bug.

        Returns:
            False
        """
        return False


class OverpaymentsStream(PaginatedStream):
    """Overpayments stream."""

    name = "overpayments"
    path = "/Overpayments"
    primary_keys = ["OverpaymentID"]
    replication_key = "UpdatedDateUTC"
    records_jsonpath = "$.Overpayments[*]"

    schema = th.PropertiesList(
        th.Property("OverpaymentID", th.StringType),
        th.Property("Type", th.StringType),
        th.Property("Contact", th.ObjectType()),
        th.Property("Date", th.StringType),
        th.Property("Status", th.StringType),
        th.Property("LineAmountTypes", th.StringType),
        th.Property("LineItems", th.ArrayType(th.ObjectType())),
        th.Property("SubTotal", th.NumberType),
        th.Property("TotalTax", th.NumberType),
        th.Property("Total", th.NumberType),
        th.Property("UpdatedDateUTC", th.StringType),
        th.Property("CurrencyCode", th.StringType),
        th.Property("CurrencyRate", th.NumberType),
        th.Property("RemainingCredit", th.NumberType),
        th.Property("Allocations", th.ArrayType(th.ObjectType())),
        th.Property("HasAttachments", th.BooleanType),
    ).to_dict()


class PaymentsStream(PaginatedStream):
    """Payments stream."""

    name = "payments"
    path = "/Payments"
    primary_keys = ["PaymentID"]
    replication_key = "UpdatedDateUTC"
    records_jsonpath = "$.Payments[*]"

    schema = th.PropertiesList(
        th.Property("PaymentID", th.StringType),
        th.Property("Date", th.StringType),
        th.Property("Amount", th.NumberType),
        th.Property("Reference", th.StringType),
        th.Property("CurrencyRate", th.NumberType),
        th.Property("PaymentType", th.StringType),
        th.Property("Status", th.StringType),
        th.Property("UpdatedDateUTC", th.StringType),
        th.Property("Invoice", th.ObjectType()),
        th.Property("CreditNote", th.ObjectType()),
        th.Property("Prepayment", th.ObjectType()),
        th.Property("Overpayment", th.ObjectType()),
        th.Property("Account", th.ObjectType()),
        th.Property("IsReconciled", th.BooleanType),
        th.Property("HasAccount", th.BooleanType),
        th.Property("HasValidationErrors", th.BooleanType),
        th.Property("BatchPaymentID", th.StringType),
        th.Property("BatchPayment", th.ObjectType()),
        th.Property("BankAmount", th.NumberType),
    ).to_dict()


class PrepaymentsStream(PaginatedStream):
    """Prepayments stream."""

    name = "prepayments"
    path = "/Prepayments"
    primary_keys = ["PrepaymentID"]
    replication_key = "UpdatedDateUTC"
    records_jsonpath = "$.Prepayments[*]"

    schema = th.PropertiesList(
        th.Property("PrepaymentID", th.StringType),
        th.Property("Type", th.StringType),
        th.Property("Contact", th.ObjectType()),
        th.Property("Date", th.StringType),
        th.Property("Status", th.StringType),
        th.Property("LineAmountTypes", th.StringType),
        th.Property("LineItems", th.ArrayType(th.ObjectType())),
        th.Property("SubTotal", th.NumberType),
        th.Property("TotalTax", th.NumberType),
        th.Property("Total", th.NumberType),
        th.Property("UpdatedDateUTC", th.StringType),
        th.Property("CurrencyCode", th.StringType),
        th.Property("CurrencyRate", th.NumberType),
        th.Property("RemainingCredit", th.NumberType),
        th.Property("Allocations", th.ArrayType(th.ObjectType())),
        th.Property("HasAttachments", th.BooleanType),
    ).to_dict()


class PurchaseOrdersStream(PaginatedStream):
    """Purchase Orders stream."""

    name = "purchase_orders"
    path = "/PurchaseOrders"
    primary_keys = ["PurchaseOrderID"]
    replication_key = "UpdatedDateUTC"
    records_jsonpath = "$.PurchaseOrders[*]"

    schema = th.PropertiesList(
        th.Property("PurchaseOrderID", th.StringType),
        th.Property("PurchaseOrderNumber", th.StringType),
        th.Property("DateString", th.StringType),
        th.Property("Date", th.StringType),
        th.Property("DeliveryDateString", th.StringType),
        th.Property("DeliveryDate", th.StringType),
        th.Property("DeliveryAddress", th.StringType),
        th.Property("AttentionTo", th.StringType),
        th.Property("Telephone", th.StringType),
        th.Property("DeliveryInstructions", th.StringType),
        th.Property("Status", th.StringType),
        th.Property("LineAmountTypes", th.StringType),
        th.Property("LineItems", th.ArrayType(th.ObjectType())),
        th.Property("SubTotal", th.NumberType),
        th.Property("TotalTax", th.NumberType),
        th.Property("Total", th.NumberType),
        th.Property("UpdatedDateUTC", th.StringType),
        th.Property("CurrencyCode", th.StringType),
        th.Property("CurrencyRate", th.NumberType),
        th.Property("Contact", th.ObjectType()),
        th.Property("BrandingThemeID", th.StringType),
        th.Property("HasAttachments", th.BooleanType),
        th.Property("HasErrors", th.BooleanType),
        th.Property("IsDiscounted", th.BooleanType),
        th.Property("Reference", th.StringType),
        th.Property("Type", th.StringType),
        th.Property("ExpectedArrivalDateString", th.StringType),
        th.Property("ExpectedArrivalDate", th.StringType),
    ).to_dict()


# Journal Stream (special pagination)


class JournalsStream(XeroStream):
    """Journals stream with special pagination using JournalNumber."""

    name = "journals"
    path = "/Journals"
    primary_keys = ["JournalID"]
    replication_key = "JournalNumber"
    records_jsonpath = "$.Journals[*]"

    is_sorted = True

    schema = th.PropertiesList(
        th.Property("JournalID", th.StringType),
        th.Property("JournalDate", th.StringType),
        th.Property("JournalNumber", th.IntegerType),
        th.Property("CreatedDateUTC", th.StringType),
        th.Property("Reference", th.StringType),
        th.Property("SourceID", th.StringType),
        th.Property("SourceType", th.StringType),
        th.Property("JournalLines", th.ArrayType(th.ObjectType())),
    ).to_dict()

    @override
    def get_url_params(
        self,
        context: Context | None,
        next_page_token: int | None,
    ) -> dict[str, Any]:
        """Get URL query parameters.

        Args:
            context: Stream partition or context dictionary
            next_page_token: Token for pagination (journal number)

        Returns:
            Dictionary of query parameters
        """
        params: dict[str, Any] = {}

        # Journals use offset parameter with journal number
        starting_journal_number: int | None
        if next_page_token:
            params["offset"] = next_page_token
        elif starting_journal_number := self.get_starting_replication_key_value(context):
            params["offset"] = starting_journal_number

        return params

    @override
    @property
    def http_headers(self) -> dict[str, str]:
        """Return headers for HTTP requests."""
        headers = super().http_headers
        # The replication key is the journal number, so we don't need to use the If-Modified-Since header.
        headers.pop("If-Modified-Since", None)
        return headers

    def get_next_page_token(
        self,
        response: requests.Response,
        previous_token: Any | None,  # noqa: ARG002
    ) -> Any | None:
        """Get next page token based on journal numbers.

        Args:
            response: HTTP response
            previous_token: Previous journal number

        Returns:
            Next journal number or None
        """
        data = response.json()
        journals: list[dict]
        if journals := data.get("Journals"):
            # Return the highest journal number seen
            return journals[-1]["JournalNumber"]

        return None


# Generic Bookmarked Streams (7)


class AccountsStream(XeroStream):
    """Accounts stream."""

    name = "accounts"
    path = "/Accounts"
    primary_keys = ["AccountID"]
    replication_key = "UpdatedDateUTC"
    records_jsonpath = "$.Accounts[*]"

    schema = th.PropertiesList(
        th.Property("AccountID", th.StringType),
        th.Property("Code", th.StringType),
        th.Property("Name", th.StringType),
        th.Property("Status", th.StringType),
        th.Property("Type", th.StringType),
        th.Property("TaxType", th.StringType),
        th.Property("Description", th.StringType),
        th.Property("Class", th.StringType),
        th.Property("SystemAccount", th.StringType),
        th.Property("EnablePaymentsToAccount", th.BooleanType),
        th.Property("ShowInExpenseClaims", th.BooleanType),
        th.Property("BankAccountNumber", th.StringType),
        th.Property("BankAccountType", th.StringType),
        th.Property("CurrencyCode", th.StringType),
        th.Property("ReportingCode", th.StringType),
        th.Property("ReportingCodeName", th.StringType),
        th.Property("HasAttachments", th.BooleanType),
        th.Property("UpdatedDateUTC", th.StringType),
        th.Property("AddToWatchlist", th.BooleanType),
    ).to_dict()


class BankTransfersStream(XeroStream):
    """Bank Transfers stream."""

    name = "bank_transfers"
    path = "/BankTransfers"
    primary_keys = ["BankTransferID"]
    replication_key = "CreatedDateUTC"  # Note: Uses CreatedDateUTC, not UpdatedDateUTC
    records_jsonpath = "$.BankTransfers[*]"

    schema = th.PropertiesList(
        th.Property("BankTransferID", th.StringType),
        th.Property("FromBankAccount", th.ObjectType()),
        th.Property("ToBankAccount", th.ObjectType()),
        th.Property("Amount", th.NumberType),
        th.Property("Date", th.StringType),
        th.Property("DateString", th.StringType),
        th.Property("FromBankTransactionID", th.StringType),
        th.Property("ToBankTransactionID", th.StringType),
        th.Property("HasAttachments", th.BooleanType),
        th.Property("CreatedDateUTC", th.StringType),
    ).to_dict()


class EmployeesStream(XeroStream):
    """Employees stream."""

    name = "employees"
    path = "/Employees"
    primary_keys = ["EmployeeID"]
    replication_key = "UpdatedDateUTC"
    records_jsonpath = "$.Employees[*]"

    schema = th.PropertiesList(
        th.Property("EmployeeID", th.StringType),
        th.Property("Status", th.StringType),
        th.Property("FirstName", th.StringType),
        th.Property("LastName", th.StringType),
        th.Property("ExternalLink", th.ObjectType()),
        th.Property("UpdatedDateUTC", th.StringType),
    ).to_dict()


class ExpenseClaimsStream(XeroStream):
    """Expense Claims stream."""

    name = "expense_claims"
    path = "/ExpenseClaims"
    primary_keys = ["ExpenseClaimID"]
    replication_key = "UpdatedDateUTC"
    records_jsonpath = "$.ExpenseClaims[*]"

    schema = th.PropertiesList(
        th.Property("ExpenseClaimID", th.StringType),
        th.Property("Status", th.StringType),
        th.Property("User", th.ObjectType()),
        th.Property("Receipts", th.ArrayType(th.ObjectType())),
        th.Property("Payments", th.ArrayType(th.ObjectType())),
        th.Property("Total", th.NumberType),
        th.Property("AmountDue", th.NumberType),
        th.Property("AmountPaid", th.NumberType),
        th.Property("PaymentDueDate", th.StringType),
        th.Property("ReportingDate", th.StringType),
        th.Property("ReceiptID", th.StringType),
        th.Property("UpdatedDateUTC", th.StringType),
    ).to_dict()


class ItemsStream(XeroStream):
    """Items stream."""

    name = "items"
    path = "/Items"
    primary_keys = ["ItemID"]
    replication_key = "UpdatedDateUTC"
    records_jsonpath = "$.Items[*]"

    schema = th.PropertiesList(
        th.Property("ItemID", th.StringType),
        th.Property("Code", th.StringType),
        th.Property("Name", th.StringType),
        th.Property("IsSold", th.BooleanType),
        th.Property("IsPurchased", th.BooleanType),
        th.Property("Description", th.StringType),
        th.Property("PurchaseDescription", th.StringType),
        th.Property("PurchaseDetails", th.ObjectType()),
        th.Property("SalesDetails", th.ObjectType()),
        th.Property("IsTrackedAsInventory", th.BooleanType),
        th.Property("InventoryAssetAccountCode", th.StringType),
        th.Property("TotalCostPool", th.NumberType),
        th.Property("QuantityOnHand", th.NumberType),
        th.Property("UpdatedDateUTC", th.StringType),
    ).to_dict()


class ReceiptsStream(XeroStream):
    """Receipts stream."""

    name = "receipts"
    path = "/Receipts"
    primary_keys = ["ReceiptID"]
    replication_key = "UpdatedDateUTC"
    records_jsonpath = "$.Receipts[*]"

    schema = th.PropertiesList(
        th.Property("ReceiptID", th.StringType),
        th.Property("ReceiptNumber", th.StringType),
        th.Property("Status", th.StringType),
        th.Property("User", th.ObjectType()),
        th.Property("Contact", th.ObjectType()),
        th.Property("Date", th.StringType),
        th.Property("DateString", th.StringType),
        th.Property("LineAmountTypes", th.StringType),
        th.Property("LineItems", th.ArrayType(th.ObjectType())),
        th.Property("SubTotal", th.NumberType),
        th.Property("TotalTax", th.NumberType),
        th.Property("Total", th.NumberType),
        th.Property("Reference", th.StringType),
        th.Property("UpdatedDateUTC", th.StringType),
        th.Property("HasAttachments", th.BooleanType),
    ).to_dict()


class UsersStream(XeroStream):
    """Users stream."""

    name = "users"
    path = "/Users"
    primary_keys = ["UserID"]
    replication_key = "UpdatedDateUTC"
    records_jsonpath = "$.Users[*]"

    schema = th.PropertiesList(
        th.Property("UserID", th.StringType),
        th.Property("EmailAddress", th.StringType),
        th.Property("FirstName", th.StringType),
        th.Property("LastName", th.StringType),
        th.Property("UpdatedDateUTC", th.StringType),
        th.Property("IsSubscriber", th.BooleanType),
        th.Property("OrganisationRole", th.StringType),
        th.Property("GlobalUserID", th.StringType),
    ).to_dict()


# Full Table Streams (8)


class BrandingThemesStream(FullTableStream):
    """Branding Themes stream."""

    name = "branding_themes"
    path = "/BrandingThemes"
    primary_keys = ["BrandingThemeID"]
    records_jsonpath = "$.BrandingThemes[*]"

    schema = th.PropertiesList(
        th.Property("BrandingThemeID", th.StringType),
        th.Property("Name", th.StringType),
        th.Property("LogoUrl", th.StringType),
        th.Property("Type", th.StringType),
        th.Property("SortOrder", th.IntegerType),
        th.Property("CreatedDateUTC", th.StringType),
    ).to_dict()


class ContactGroupsStream(FullTableStream):
    """Contact Groups stream."""

    name = "contact_groups"
    path = "/ContactGroups"
    primary_keys = ["ContactGroupID"]
    records_jsonpath = "$.ContactGroups[*]"

    schema = th.PropertiesList(
        th.Property("ContactGroupID", th.StringType),
        th.Property("Name", th.StringType),
        th.Property("Status", th.StringType),
        th.Property("Contacts", th.ArrayType(th.ObjectType())),
        th.Property("HasValidationErrors", th.BooleanType),
    ).to_dict()


class CurrenciesStream(FullTableStream):
    """Currencies stream."""

    name = "currencies"
    path = "/Currencies"
    primary_keys = ["Code"]
    records_jsonpath = "$.Currencies[*]"

    schema = th.PropertiesList(
        th.Property("Code", th.StringType),
        th.Property("Description", th.StringType),
    ).to_dict()


class OrganisationsStream(FullTableStream):
    """Organisations stream."""

    name = "organisations"
    path = "/Organisations"
    primary_keys = ["OrganisationID"]
    records_jsonpath = "$.Organisations[*]"

    schema = th.PropertiesList(
        th.Property("OrganisationID", th.StringType),
        th.Property("APIKey", th.StringType),
        th.Property("Name", th.StringType),
        th.Property("LegalName", th.StringType),
        th.Property("PaysTax", th.BooleanType),
        th.Property("Version", th.StringType),
        th.Property("OrganisationType", th.StringType),
        th.Property("BaseCurrency", th.StringType),
        th.Property("CountryCode", th.StringType),
        th.Property("IsDemoCompany", th.BooleanType),
        th.Property("OrganisationStatus", th.StringType),
        th.Property("RegistrationNumber", th.StringType),
        th.Property("TaxNumber", th.StringType),
        th.Property("FinancialYearEndDay", th.IntegerType),
        th.Property("FinancialYearEndMonth", th.IntegerType),
        th.Property("SalesTaxBasis", th.StringType),
        th.Property("SalesTaxPeriod", th.StringType),
        th.Property("DefaultSalesTax", th.StringType),
        th.Property("DefaultPurchasesTax", th.StringType),
        th.Property("PeriodLockDate", th.StringType),
        th.Property("EndOfYearLockDate", th.StringType),
        th.Property("CreatedDateUTC", th.StringType),
        th.Property("Timezone", th.StringType),
        th.Property("OrganisationEntityType", th.StringType),
        th.Property("ShortCode", th.StringType),
        th.Property("LineOfBusiness", th.StringType),
        th.Property("Addresses", th.ArrayType(th.ObjectType())),
        th.Property("Phones", th.ArrayType(th.ObjectType())),
        th.Property("ExternalLinks", th.ArrayType(th.ObjectType())),
        th.Property("PaymentTerms", th.ObjectType()),
        th.Property("Edition", th.StringType),
        th.Property("Class", th.StringType),
        th.Property("TaxNumberName", th.StringType),
    ).to_dict()


class RepeatingInvoicesStream(FullTableStream):
    """Repeating Invoices stream."""

    name = "repeating_invoices"
    path = "/RepeatingInvoices"
    primary_keys = ["RepeatingInvoiceID"]
    records_jsonpath = "$.RepeatingInvoices[*]"

    schema = th.PropertiesList(
        th.Property("RepeatingInvoiceID", th.StringType),
        th.Property("Type", th.StringType),
        th.Property("Contact", th.ObjectType()),
        th.Property("Schedule", th.ObjectType()),
        th.Property("LineItems", th.ArrayType(th.ObjectType())),
        th.Property("LineAmountTypes", th.StringType),
        th.Property("Reference", th.StringType),
        th.Property("BrandingThemeID", th.StringType),
        th.Property("CurrencyCode", th.StringType),
        th.Property("Status", th.StringType),
        th.Property("SubTotal", th.NumberType),
        th.Property("TotalTax", th.NumberType),
        th.Property("Total", th.NumberType),
        th.Property("HasAttachments", th.BooleanType),
        th.Property("ApprovedForSending", th.BooleanType),
        th.Property("SendCopy", th.BooleanType),
        th.Property("MarkAsSent", th.BooleanType),
        th.Property("IncludePDF", th.BooleanType),
        th.Property("ID", th.StringType),
        th.Property("UpdatedDateUTC", th.StringType),
    ).to_dict()


class TaxRatesStream(FullTableStream):
    """Tax Rates stream."""

    name = "tax_rates"
    path = "/TaxRates"
    primary_keys = ["Name"]
    records_jsonpath = "$.TaxRates[*]"

    schema = th.PropertiesList(
        th.Property("Name", th.StringType),
        th.Property("TaxType", th.StringType),
        th.Property("TaxComponents", th.ArrayType(th.ObjectType())),
        th.Property("Status", th.StringType),
        th.Property("ReportTaxType", th.StringType),
        th.Property("CanApplyToAssets", th.BooleanType),
        th.Property("CanApplyToEquity", th.BooleanType),
        th.Property("CanApplyToExpenses", th.BooleanType),
        th.Property("CanApplyToLiabilities", th.BooleanType),
        th.Property("CanApplyToRevenue", th.BooleanType),
        th.Property("DisplayTaxRate", th.NumberType),
        th.Property("EffectiveRate", th.NumberType),
    ).to_dict()


class TrackingCategoriesStream(FullTableStream):
    """Tracking Categories stream."""

    name = "tracking_categories"
    path = "/TrackingCategories"
    primary_keys = ["TrackingCategoryID"]
    records_jsonpath = "$.TrackingCategories[*]"

    schema = th.PropertiesList(
        th.Property("TrackingCategoryID", th.StringType),
        th.Property("Name", th.StringType),
        th.Property("Status", th.StringType),
        th.Property("Options", th.ArrayType(th.ObjectType())),
    ).to_dict()


class LinkedTransactionsStream(FullTableStream):
    """Linked Transactions stream."""

    name = "linked_transactions"
    path = "/LinkedTransactions"
    primary_keys = ["LinkedTransactionID"]
    records_jsonpath = "$.LinkedTransactions[*]"

    schema = th.PropertiesList(
        th.Property("LinkedTransactionID", th.StringType),
        th.Property("SourceTransactionID", th.StringType),
        th.Property("SourceLineItemID", th.StringType),
        th.Property("ContactID", th.StringType),
        th.Property("TargetTransactionID", th.StringType),
        th.Property("TargetLineItemID", th.StringType),
        th.Property("Type", th.StringType),
        th.Property("Status", th.StringType),
        th.Property("UpdatedDateUTC", th.StringType),
    ).to_dict()
