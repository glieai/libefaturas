# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2025-01-06

### Added
- Integration guide (`docs/INTEGRATION.md`) explaining app-side vs library responsibilities
- Custom exception hierarchy (`EFaturasError`, `EFaturasConnectionError`, `EFaturasAuthError`, `EFaturasSOAPError`, `EFaturasValidationError`, `EFaturasRetryError`, `EFaturasKeyError`)
- Automatic retry logic with exponential backoff for transient failures
- `RetryConfig` dataclass for customizing retry behavior
- Portuguese tax utilities module (`pt_utils`):
  - `extract_hash_chars()` - Extract 4 hash characters for QR code/documents
  - `extract_hash_control()` - Extract HashControl for SAF-T
  - `format_invoice_no()` - Format SAF-T InvoiceNo
  - `format_atcud()` - Format ATCUD codes
  - `build_qr_payload()` - Build AT-compliant QR code payload
  - `generate_qr_png()` - Generate QR code PNG image
  - `classify_tax_rate()` - Classify VAT rates (ISE/RED/INT/NOR)
  - `get_tax_rate()` - Get regional tax rates (PT/PT-MA/PT-AC)
  - `calculate_tax_totals()` - Calculate tax breakdown by rate category
  - `get_document_section()` - Map document type to SAF-T section
  - `q2()` / `q6()` - Decimal formatting utilities
- Pre-commit hooks configuration (ruff, mypy)
- Ruff configuration for linting and formatting
- Comprehensive test suite (74 tests)

### Changed
- `_WSClient.post()` now uses retry logic by default (configurable)
- Improved error messages with more context

## [0.1.0] - 2025-01-06

### Added
- Initial open source release
- Core cryptographic functions for AT WS-Security (UsernameToken)
- SAF-T hash generation (RSA-PKCS1v15-SHA1)
- Series management (SeriesWS) client
- Invoice/Work/Payment communication (FatcoreWS) client
- High-level `EFaturasClient` API
- Test suite with pytest
- CI/CD pipeline with GitHub Actions

### Security
- All cryptographic operations use the `cryptography` library
- Symmetric encryption: AES-128-ECB with PKCS7 padding
- Asymmetric encryption: RSA with PKCS#1 v1.5 padding
- Hash signatures: RSA-PKCS1v15-SHA1 (as required by AT)
