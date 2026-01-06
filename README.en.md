# libefaturas

Python library for communicating with the official Portuguese Tax Authority (AT) webservices (e-Fatura / SeriesWS) with a minimal API: a single client and uniform results.

- Automatic UsernameToken / WS-Security generation
- Series communication (SeriesWS) and invoices/works/payments (FatcoreWS)
- Simple signatures with built-in types (`str`, `int`, `date`, `dict`, `list`)
- Response always in the same format (`EFaturasResult`: `ok`, `code`, `message`, `data`)

## Quick Installation

```bash
pip install libefaturas
```

Prerequisites:

- Python 3.9+
- Software producer certificate issued by AT (`.crt/.pem` + private key)
- User/sub-user credentials with WSE permissions
- Public key from the Authentication System (`.cer` or `.pem`)

## High-Level API

```python
from libefaturas import EFaturasClient

client = EFaturasClient(
    username="599999993/37",                  # WSE user/sub-user
    password="PORTAL_PASSWORD",
    public_key_path="certs/at_public_key.cer",
    client_cert_path="certs/software.crt.pem",
    client_key_path="certs/software.key.pem",
    ca_cert_path="certs/ca_at.pem",           # optional (uses system truststore if omitted)
    environment="test",                       # or "prod"
)
```

### Standard Result

All operations return an `EFaturasResult`:

- `ok`: `True` if AT accepted the operation
- `code`: AT numeric code (when available)
- `message`: Human-readable message
- `data`: Useful payload (e.g., list of series)

### Test Connection

```python
result = client.test_connection(service="faturas")  # or "series"
if not result.ok:
    print(result.message, result.data)
```

### Communicate Invoices / Works / Payments (FatcoreWS)

Methods accept dictionaries equivalent to AT manual fields. The library validates, converts to required payloads, and handles SOAP/TLS.

```python
from datetime import date, datetime
from decimal import Decimal

invoice_data = {
    "InvoiceNo": "FT A/2024/1",
    "ATCUD": "ATCUD-EXAMPLE",
    "InvoiceDate": date(2024, 1, 15),
    "InvoiceType": "FT",
    "SelfBillingIndicator": 0,
    "CustomerTaxID": "999999990",
    "CustomerTaxIDCountry": "PT",
    "DocumentStatus": {"InvoiceStatus": "N", "InvoiceStatusDate": datetime.now()},
    "HashCharacters": "ABCD",
    "CashVATSchemeIndicator": 0,
    "PaperlessIndicator": 1,
    "SystemEntryDate": datetime.now(),
    "LineSummary": [
        {
            "TaxPointDate": date(2024, 1, 15),
            "DebitCreditIndicator": "D",
            "TotalTaxBase": Decimal("100.00"),
            "Tax": {
                "TaxType": "IVA",
                "TaxCountryRegion": "PT",
                "TaxCode": "NOR",
                "TaxPercentage": Decimal("23.00"),
            },
        }
    ],
    "DocumentTotals": {
        "TaxPayable": Decimal("23.00"),
        "NetTotal": Decimal("100.00"),
        "GrossTotal": Decimal("123.00"),
    },
}

result = client.register_invoice(
    efatura_md_version="0.0.1",
    audit_file_version="1.04_01",
    tax_registration_number="599999993",
    tax_entity="Global",
    software_certificate_number=9999,
    invoice_data=invoice_data,
    canal_registo={"Sistema": "MyApp", "Versao": "1.0.0"},
)

if not result.ok:
    print(result.code, result.message)
```

Available methods (all return `EFaturasResult`): `register_invoice`, `change_invoice_status`, `delete_invoice`, `register_work`, `change_work_status`, `delete_work`, `register_payment`, `change_payment_status`, `delete_payment`.

### Communicate Series (SeriesWS)

```python
from datetime import date

create = client.create_series(
    serie="A",
    tipo_serie="N",
    classe_doc="FT",
    tipo_doc="FT",
    num_inicial_seq=1,
    data_inicio=date(2024, 1, 1),
    num_cert_sw="9999",            # software certificate or "0"
    meio_processamento="PI",       # as per AT manual
)
print(create.ok, create.code, create.message, create.data)

series_list = client.list_series(estado="A", tipo_doc="FT")
for serie in series_list.data or []:
    print(serie.serie, serie.estado, serie.codigo_validacao)

finalize = client.finalize_series(
    serie="A",
    classe_doc="FT",
    tipo_doc="FT",
    codigo_validacao="X1Y2Z3A4",
    seq_ultimo_doc_emitido=120,
    justificacao="Series replaced",
)
print(finalize.ok, finalize.message)
```

Other methods: `cancel_series`.

## SAF-T Hash Generation

For SAF-T document signing:

```python
from libefaturas.security import gerar_hash_fatura

# Generate hash for invoice
document_hash = gerar_hash_fatura(
    invoice_date="2025-01-15",
    system_entry_date="2025-01-15T10:30:00",
    invoice_no="FT FT2025/000001",
    gross_total="123.00",
    previous_hash="",  # Empty for first document
    saft_private_key_path="path/to/saft_key.pem",
    saft_private_key_password=b"key_password",
)
```

## Portuguese Tax Utilities

The `pt_utils` module provides reusable utilities for Portuguese invoicing compliance:

```python
from libefaturas.pt_utils import (
    extract_hash_chars,
    format_invoice_no,
    format_atcud,
    build_qr_payload,
    generate_qr_png,
    classify_tax_rate,
    get_tax_rate,
    PT_TAX_RATES,
)

# Extract 4 hash characters for QR code (positions 1, 11, 21, 31)
hash_chars = extract_hash_chars(document_hash)  # e.g., "ABCD"

# Format document number (SAF-T InvoiceNo format)
invoice_no = format_invoice_no("FT", "FT2025", 1)  # "FT FT2025/000001"

# Format ATCUD
atcud = format_atcud("FTAA0001", 1)  # "FTAA0001-000001"

# Build QR code payload
payload = build_qr_payload(
    issuer_vat="123456789",
    customer_vat="999999990",
    customer_country="PT",
    doc_type="FT",
    doc_status="N",
    doc_date=date(2025, 1, 15),
    doc_no="FT FT2025/000001",
    atcud="FTAA0001-000001",
    total_tax=Decimal("23"),
    total_gross=Decimal("123"),
    hash_chars="ABCD",
    cert_number=9999,
)

# Generate QR code PNG (requires qrcode[pil])
png_bytes = generate_qr_png(payload)

# Get tax rate for a region
rate = get_tax_rate("PT", "NOR")  # Decimal("23")
rate_madeira = get_tax_rate("PT-MA", "NOR")  # Decimal("22")
```

## Error Handling

The library provides custom exceptions for precise error handling:

```python
from libefaturas import (
    EFaturasError,           # Base exception for all errors
    EFaturasConnectionError, # Network/TLS failures
    EFaturasAuthError,       # Authentication failures
    EFaturasSOAPError,       # SOAP faults from AT
    EFaturasValidationError, # Input validation errors
    EFaturasRetryError,      # All retry attempts exhausted
    EFaturasKeyError,        # Cryptographic key issues
)

try:
    result = client.register_invoice(...)
except EFaturasConnectionError as e:
    print(f"Connection failed to {e.endpoint}: {e.message}")
except EFaturasAuthError as e:
    print(f"Auth failed: {e.fault_code} - {e.fault_string}")
except EFaturasError as e:
    print(f"General error: {e.message}")
```

## Retry Configuration

The client automatically retries on transient failures (connection resets, timeouts, 5xx errors):

```python
from libefaturas import EFaturasClient, RetryConfig

# Custom retry configuration
retry_config = RetryConfig(
    max_attempts=5,        # Default: 3
    base_delay=2.0,        # Default: 1.0 seconds
    max_delay=60.0,        # Default: 30.0 seconds
    exponential_base=2.0,  # Exponential backoff multiplier
    jitter=0.1,            # Random jitter (0-10% of delay)
)

client = EFaturasClient(
    username="599999993/37",
    password="PASSWORD",
    public_key_path="certs/at_public_key.cer",
    client_cert_path="certs/software.crt.pem",
    client_key_path="certs/software.key.pem",
    retry_config=retry_config,  # Optional
)
```

## Notes

- Under normal conditions, the library does not raise exceptions: errors are returned as `EFaturasResult(ok=False, ...)`.
- For connection/retry errors, explicit exceptions are raised (see Error Handling above).
- Field validations follow AT manual rules; validation messages appear in `result.message`.
- If you need deep debugging, internal implementations remain available in `faturas` and `series` modules, but they are not part of the public API.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linter
ruff check src/
```

## License

MIT License - see [LICENSE](LICENSE) file.
