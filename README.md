# tap-xero

Singer tap for Xero, built with the Meltano Singer SDK.

This is a complete rewrite of the [original tap-xero](https://github.com/singer-io/tap-xero) using the [Meltano Singer SDK](https://sdk.meltano.com/), providing improved maintainability, better error handling, and modern Python practices.

## Features

- **27 Xero API streams** covering accounting transactions, contacts, invoices, and more
- **OAuth2 authentication** with automatic token refresh
- **Incremental sync support** for most streams using bookmarks
- **Sophisticated rate limiting** handling for Xero API limits
- **Custom .NET JSON date parsing** for Xero's date format
- **Archived contacts** optional inclusion
- Built on the **Meltano Singer SDK** for reliability and standardization

## Supported Streams

### Paginated Streams (Incremental)
- bank_transactions
- contacts (with optional archived contacts)
- quotes
- credit_notes
- invoices
- manual_journals
- overpayments
- payments
- prepayments
- purchase_orders

### Journal Stream (Special Incremental)
- journals (uses JournalNumber as replication key)

### Bookmarked Streams (Incremental)
- accounts
- bank_transfers
- employees
- expense_claims
- items
- receipts
- users

### Full Table Streams
- branding_themes
- contact_groups
- currencies
- organisations
- repeating_invoices
- tax_rates
- tracking_categories
- linked_transactions

## Installation

### Using pip

```bash
pip install tap-xero
```

### For Development

```bash
git clone https://github.com/Matatika/tap-xero
cd tap-xero
pip install -e .
```

### Using Poetry

```bash
poetry install
```

## Configuration

### Required Settings

- **client_id**: OAuth2 client ID for your Xero application
- **client_secret**: OAuth2 client secret for your Xero application
- **tenant_id**: Your Xero tenant/organisation ID
- **refresh_token**: OAuth2 refresh token (will be automatically updated during sync)
- **start_date**: Earliest record date to sync (ISO 8601 format, e.g., "2020-01-01T00:00:00Z")

### Optional Settings

- **user_agent**: Custom User-Agent header for API requests
- **include_archived_contacts**: Include archived contacts in the contacts stream (default: false)

### Configuration File Example

Create a `config.json` file:

```json
{
  "client_id": "YOUR_XERO_CLIENT_ID",
  "client_secret": "YOUR_XERO_CLIENT_SECRET",
  "tenant_id": "YOUR_XERO_TENANT_ID",
  "refresh_token": "YOUR_XERO_REFRESH_TOKEN",
  "start_date": "2020-01-01T00:00:00Z",
  "user_agent": "tap-xero/3.0.0",
  "include_archived_contacts": false
}
```

## Getting Xero Credentials

1. **Create a Xero App**:
   - Go to https://developer.xero.com/app/manage
   - Create a new app or use an existing one
   - Note your **Client ID** and **Client Secret**

2. **Get OAuth2 Tokens**:
   - Follow Xero's OAuth2 flow to obtain an initial **refresh_token**
   - You can use tools like Postman or write a simple OAuth2 script
   - The tap will automatically refresh tokens during sync

3. **Get Tenant ID**:
   - After obtaining an access token, call the Xero Connections API:
     ```bash
     curl https://api.xero.com/connections \
       -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
     ```
   - The response will contain your **tenant_id** (also called organisation ID)

## Usage

### Discovery Mode

Generate a catalog of available streams:

```bash
tap-xero --config config.json --discover > catalog.json
```

### Sync Mode

Extract data from Xero:

```bash
tap-xero --config config.json --catalog catalog.json --state state.json
```

### With Meltano

Add to your `meltano.yml`:

```yaml
plugins:
  extractors:
  - name: tap-xero
    namespace: tap_xero
    pip_url: tap-xero
    config:
      start_date: "2020-01-01T00:00:00Z"
```

Then run:

```bash
meltano install extractor tap-xero
meltano config tap-xero set client_id YOUR_CLIENT_ID
meltano config tap-xero set client_secret YOUR_CLIENT_SECRET
meltano config tap-xero set tenant_id YOUR_TENANT_ID
meltano config tap-xero set refresh_token YOUR_REFRESH_TOKEN
meltano elt tap-xero target-jsonl
```

## Features & Implementation Details

### OAuth2 with Automatic Refresh

The tap automatically refreshes OAuth2 tokens when they expire. Xero returns a new refresh_token with each token refresh, which is automatically updated in the configuration.

### Date Format Handling

Xero uses .NET JSON date format (`/Date(1419937200000+0000)/`). The tap automatically converts these to RFC3339 format (`2014-12-30T09:00:00.000000Z`).

### Rate Limiting

The tap handles Xero's rate limits intelligently:
- **Per-minute rate limits**: Automatically retries with exponential backoff
- **Daily rate limits**: Fails immediately with clear error message
- Uses the `Retry-After` header when provided

### Incremental Sync

Most streams support incremental sync using:
- **UpdatedDateUTC** for most streams
- **CreatedDateUTC** for bank_transfers
- **JournalNumber** for journals

The tap maintains state between runs to avoid re-processing data.

### Archived Contacts

By default, the tap excludes archived contacts. Set `include_archived_contacts: true` to include them.

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black tap_xero/
```

### Type Checking

```bash
mypy tap_xero/
```

### Linting

```bash
flake8 tap_xero/
```

## Migration from tap-xero v2.x

This v3.x release is a complete rewrite using the Meltano Singer SDK. Key differences:

1. **Configuration**: Same required fields, but now uses Singer SDK standards
2. **Schema**: Schemas are now inline in code rather than separate JSON files
3. **State handling**: Improved state management through SDK
4. **OAuth2**: Still uses refresh tokens, automatically updates them
5. **Streams**: All 27 streams from v2.x are supported

The tap should be backward compatible in terms of data output, but you may need to:
- Update your catalog selection if you have a saved catalog
- Verify schema compatibility with your target

## Troubleshooting

### "Unauthorized (401)" errors

- Your refresh_token may have expired (Xero tokens expire after 60 days of inactivity)
- Regenerate OAuth2 tokens through the Xero OAuth2 flow

### "Rate limit exceeded (429)" errors

- **Per-minute limit**: The tap will automatically retry
- **Daily limit**: You've exceeded Xero's daily API call limit (5,000 calls/day for most plans)
  - Wait until the next day (UTC)
  - Consider reducing the frequency of syncs

### "Invalid tenant_id" errors

- Verify your tenant_id matches your Xero organisation
- Call the Xero Connections API to get the correct tenant_id

### Missing or incorrect data

- Check your `start_date` configuration
- Verify stream selection in your catalog
- Review Xero permissions for your OAuth2 app

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details

## Links

- [Xero API Documentation](https://developer.xero.com/documentation/api/accounting/overview)
- [Singer Specification](https://github.com/singer-io/getting-started/blob/master/docs/SPEC.md)
- [Meltano Singer SDK](https://sdk.meltano.com/)
- [Original tap-xero](https://github.com/singer-io/tap-xero)

## Maintainers

- [Matatika](https://github.com/Matatika)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

---

Built with ❤️ using the [Meltano Singer SDK](https://sdk.meltano.com/)
