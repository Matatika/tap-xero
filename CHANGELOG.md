# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
- Replace Black and flake8 with Ruff
- Migrate project to use PEP 621

## [4.0.0] - 2025-12-22

### Breaking Changes

- **Configuration schema changed to nested structure with `oauth_credentials` object**

  All OAuth settings now nested under `oauth_credentials`:
  - `oauth_credentials.client_id`
  - `oauth_credentials.client_secret`
  - `oauth_credentials.refresh_token`
  - `oauth_credentials.refresh_proxy_url` (new)
  - `oauth_credentials.refresh_proxy_url_auth` (new)

## [3.0.0] - 2025-12-05

### Changed
- **BREAKING**: Complete rewrite using Meltano Singer SDK
- Migrated from custom Singer implementation to SDK-based architecture
- OAuth2 implementation now uses SDK authenticators
- Schemas are now defined inline in code rather than separate JSON files
- Improved error handling and retry logic
- Enhanced rate limiting handling for Xero API
- Better state management through SDK

### Added
- Support for all 27 Xero API streams from v2.x
- Automatic OAuth2 token refresh
- Custom .NET JSON date format parsing
- Sophisticated rate limit handling (minute and daily limits)
- Incremental sync support for most streams
- Optional archived contacts inclusion
- Comprehensive documentation and examples
- Meltano configuration file
- Development tools configuration (Black, mypy, flake8)

### Maintained
- All stream support from v2.x
- OAuth2 authentication flow
- Incremental sync with bookmarks
- Configuration compatibility (same required fields)

## [2.3.2] - Previous Version

See [original tap-xero repository](https://github.com/singer-io/tap-xero) for earlier version history.

[3.0.0]: https://github.com/Matatika/tap-xero/releases/tag/v3.0.0
