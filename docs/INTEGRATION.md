# libefaturas Integration Guide

This guide explains what you need to implement in your application to achieve AT (Autoridade Tributária) certification, and what libefaturas handles for you.

## Overview

AT certification for Portuguese invoicing requires:
1. **SAF-T PT File Generation** - Standard Audit File for Tax (XML)
2. **Document Hashing** - Cryptographic signature chain
3. **QR Code** - Machine-readable tax information
4. **ATCUD** - Unique document code
5. **Real-time Communication** - Series registration and invoice reporting

### What libefaturas Provides (Library-Side)

| Feature | Module | Description |
|---------|--------|-------------|
| WS-Security | `security` | UsernameToken generation, AES/RSA encryption |
| Hash Generation | `security.gerar_hash_fatura()` | RSA-PKCS1v15-SHA1 document signatures |
| Series Registration | `client.create_series()` | SeriesWS API communication |
| Invoice Communication | `client.register_invoice()` | FatcoreWS API communication |
| QR Code Payload | `pt_utils.build_qr_payload()` | AT-compliant QR code content |
| QR Code Image | `pt_utils.generate_qr_png()` | PNG generation |
| Hash Characters | `pt_utils.extract_hash_chars()` | Extract 4 chars for QR field Q |
| Tax Rate Tables | `pt_utils.PT_TAX_RATES` | Official PT/Madeira/Azores rates |
| ATCUD Formatting | `pt_utils.format_atcud()` | Validation code + sequence |
| Document Numbering | `pt_utils.format_invoice_no()` | SAF-T InvoiceNo format |
| Error Handling | `exceptions` | Typed exceptions for all failure modes |
| Retry Logic | `retry` | Automatic retries with backoff |

### What Your Application Must Implement (App-Side)

| Feature | Description | SAF-T Field |
|---------|-------------|-------------|
| Document Storage | Store invoices, credit notes, etc. in database | All 4.1.x fields |
| Sequential Numbering | Maintain gap-free sequences per series | InvoiceNo |
| Hash Chain | Store previous hash, link to next document | Hash, HashControl |
| Customer Master | Name, VAT, address | Customer section |
| Product Catalog | Code, description, unit of measure | Product section |
| Tax Calculation | Apply correct rates, handle exemptions | Tax section |
| Report Templates | PDF/printed documents with AT compliance | N/A |
| SAF-T XML Generation | Build complete XML from your data | Entire file |
| Audit Trail | Track all document changes | N/A |
| User Interface | Forms, lists, wizards | N/A |

---

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         YOUR APPLICATION                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │  Database   │  │   Invoice   │  │   Report    │  │   SAF-T    │  │
│  │  Storage    │  │   Logic     │  │  Templates  │  │  Generator │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘  │
│         │                │                │                │        │
│         └────────────────┴────────────────┴────────────────┘        │
│                                  │                                   │
│                                  ▼                                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    libefaturas                                │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐    │   │
│  │  │   security   │  │    client    │  │     pt_utils     │    │   │
│  │  │  Hash Gen    │  │  SeriesWS    │  │  QR Code Build   │    │   │
│  │  │  WS-Security │  │  FatcoreWS   │  │  Format Helpers  │    │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │   AT Webservices        │
                    │   SeriesWS / FatcoreWS  │
                    └─────────────────────────┘
```

---

## Step-by-Step Integration

### Step 1: Certificate Setup (App-Side)

Before using libefaturas, you need these certificates from AT:

```
your_app/
└── certs/
    ├── software.crt.pem     # Your software producer certificate
    ├── software.key.pem     # Your software producer private key
    ├── saft_private.pem     # SAF-T signing key (1024-bit RSA)
    └── at_public_key.cer    # AT's public key for encryption
```

**App responsibility**: Store certificate paths securely, manage key rotation.

### Step 2: Company Configuration (App-Side)

Your application must store and validate:

```python
# Example: Required company configuration fields
company_config = {
    "vat": "PT508025338",           # Portuguese VAT number
    "name": "Empresa Exemplo, Lda",
    "address": {
        "street": "Rua Exemplo 123",
        "city": "Lisboa",
        "postal_code": "1000-001",
        "country": "PT",
    },
    # AT credentials (for real-time communication)
    "wfa_username": "508025338/1",   # VAT/subuser
    "wfa_password": "portal_password",
    # Certificate paths
    "software_cert_path": "/path/to/software.crt.pem",
    "software_key_path": "/path/to/software.key.pem",
    "saft_key_path": "/path/to/saft_private.pem",
    "at_public_key_path": "/path/to/at_public_key.cer",
    # Software certificate number (from Modelo 24)
    "software_cert_number": 9999,
}
```

### Step 3: Document Series Management (App-Side + Library)

#### 3.1 Create Sequence in Your Database (App-Side)

```python
# Your app must maintain sequences
sequence = {
    "id": 1,
    "series_code": "FT2025",         # Series identifier
    "document_type": "FT",            # FT, FS, NC, ND, etc.
    "prefix": "FT2025/",              # For document naming
    "next_number": 1,                 # Current sequence number
    "padding": 6,                     # Zero-pad to 6 digits
    "at_validation_code": None,       # Filled after AT registration
    "at_state": "draft",              # draft, registered, finalized
}
```

#### 3.2 Register with AT (Using libefaturas)

```python
from datetime import date
from libefaturas import EFaturasClient

client = EFaturasClient(
    username=company_config["wfa_username"],
    password=company_config["wfa_password"],
    public_key_path=company_config["at_public_key_path"],
    client_cert_path=company_config["software_cert_path"],
    client_key_path=company_config["software_key_path"],
    environment="test",  # or "prod"
)

# Register the series with AT
result = client.create_series(
    serie=sequence["series_code"],
    tipo_serie="N",                          # N=Normal
    classe_doc="FT",                         # Document class
    tipo_doc=sequence["document_type"],      # Document type
    num_inicial_seq=sequence["next_number"],
    data_inicio=date.today(),
    num_cert_sw=str(company_config["software_cert_number"]),
    meio_processamento="PI",                 # PI=Integrated Program
)

if result.ok:
    # Update your sequence with AT's validation code
    sequence["at_validation_code"] = result.data.get("codigo_validacao")
    sequence["at_state"] = "registered"
    # Save to database
else:
    raise Exception(f"Failed to register series: {result.message}")
```

### Step 4: Invoice Creation Flow (App-Side + Library)

When creating an invoice, your app must:

#### 4.1 Get Next Sequence Number (App-Side)

```python
def get_next_invoice_number(sequence):
    """Atomically get and increment sequence number."""
    # This MUST be atomic to prevent gaps
    number = sequence["next_number"]
    sequence["next_number"] += 1
    # Save to database
    return number

invoice_number = get_next_invoice_number(sequence)
# Format: "FT2025/000001"
invoice_name = f"{sequence['prefix']}{str(invoice_number).zfill(sequence['padding'])}"
```

#### 4.2 Calculate ATCUD (App-Side, using library helper)

```python
from libefaturas.pt_utils import format_atcud

# ATCUD = ValidationCode-SequenceNumber
atcud = format_atcud(
    validation_code=sequence["at_validation_code"],  # e.g., "FTAA0001"
    sequence_number=invoice_number,                   # e.g., 1
    padding=sequence["padding"],                      # e.g., 6
)
# Result: "FTAA0001-000001"
```

#### 4.3 Format Document Number for SAF-T (App-Side, using library helper)

```python
from libefaturas.pt_utils import format_invoice_no

# SAF-T InvoiceNo format: "TYPE SERIES/NUMBER"
saft_invoice_no = format_invoice_no(
    doc_type=sequence["document_type"],  # "FT"
    series_code=sequence["series_code"],  # "FT2025"
    number=invoice_number,                 # 1
    padding=sequence["padding"],           # 6
)
# Result: "FT FT2025/000001"
```

#### 4.4 Get Previous Hash (App-Side)

```python
def get_previous_hash(company_id, sequence_id):
    """Get hash from the previous document in this series."""
    # Query your database for the last signed document
    # in this company + sequence combination
    previous_doc = db.query("""
        SELECT hash FROM invoices
        WHERE company_id = ? AND sequence_id = ?
        AND hash IS NOT NULL
        ORDER BY create_date DESC, id DESC
        LIMIT 1
    """, [company_id, sequence_id])

    return previous_doc.hash if previous_doc else ""
```

#### 4.5 Generate Document Hash (Using libefaturas)

```python
from libefaturas.security import gerar_hash_fatura
from datetime import datetime
from decimal import Decimal

# Prepare invoice data
invoice_date = "2025-01-15"
system_entry_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
gross_total = str(Decimal("123.00").quantize(Decimal("0.01")))

# Get previous hash for chain
previous_hash = get_previous_hash(company_id, sequence_id)

# Generate hash using libefaturas
document_hash = gerar_hash_fatura(
    invoice_date=invoice_date,
    system_entry_date=system_entry_date,
    invoice_no=saft_invoice_no,              # "FT FT2025/000001"
    gross_total=gross_total,                  # "123.00"
    previous_hash=previous_hash,              # "" for first, previous hash otherwise
    saft_private_key_path=company_config["saft_key_path"],
    saft_private_key_password=None,           # Or bytes if encrypted
)

# Store the hash
invoice["hash"] = document_hash
invoice["previous_hash"] = previous_hash
```

#### 4.6 Generate QR Code (Using libefaturas)

```python
from libefaturas.pt_utils import build_qr_payload, generate_qr_png, extract_hash_chars
from decimal import Decimal

# Extract hash characters for QR field Q
hash_chars = extract_hash_chars(document_hash)

# Build QR payload
qr_payload = build_qr_payload(
    issuer_vat=company_config["vat"].replace("PT", ""),
    customer_vat=invoice["customer_vat"] or "999999990",
    customer_country=invoice["customer_country"] or "PT",
    doc_type=sequence["document_type"],
    doc_status="N",                           # N=Normal, A=Cancelled
    doc_date=invoice["date"],
    doc_no=saft_invoice_no,
    atcud=atcud,
    fiscal_region="PT",                       # PT, PT-AC, PT-MA
    tax_exempt_base=Decimal("0"),             # I2 field
    reduced_rate_base=Decimal("0"),           # I3 field
    reduced_rate_tax=Decimal("0"),            # I4 field
    intermediate_rate_base=Decimal("0"),      # I5 field
    intermediate_rate_tax=Decimal("0"),       # I6 field
    normal_rate_base=invoice["net_total"],    # I7 field
    normal_rate_tax=invoice["tax_total"],     # I8 field
    total_tax=invoice["tax_total"],
    total_gross=invoice["gross_total"],
    hash_chars=hash_chars,
    cert_number=company_config["software_cert_number"],
    include_markers=True,                      # A:, B:, etc. prefixes
)

# Generate PNG image
qr_png_bytes = generate_qr_png(qr_payload)

# Store for printing
invoice["qr_png"] = qr_png_bytes
```

### Step 5: SAF-T XML Generation (App-Side)

Your application must generate the complete SAF-T XML. libefaturas does NOT generate SAF-T files - this is your responsibility.

```xml
<?xml version="1.0" encoding="Windows-1252"?>
<AuditFile xmlns="urn:OECD:StandardAuditFile-Tax:PT_1.04_01">
    <Header>
        <!-- App generates this from company_config -->
    </Header>
    <MasterFiles>
        <!-- App generates from customer/product data -->
    </MasterFiles>
    <SourceDocuments>
        <SalesInvoices>
            <Invoice>
                <InvoiceNo>FT FT2025/000001</InvoiceNo>  <!-- format_invoice_no() -->
                <ATCUD>FTAA0001-000001</ATCUD>          <!-- format_atcud() -->
                <Hash>BASE64_HASH...</Hash>             <!-- gerar_hash_fatura() -->
                <HashControl>1</HashControl>            <!-- App: "1" for first, prev hash chars otherwise -->
                <!-- ... other fields from your invoice data ... -->
            </Invoice>
        </SalesInvoices>
    </SourceDocuments>
</AuditFile>
```

**Key SAF-T fields your app must provide**:

| Field | Source |
|-------|--------|
| InvoiceNo | `format_invoice_no()` |
| ATCUD | `format_atcud()` |
| Hash | `gerar_hash_fatura()` |
| HashControl | App logic: "1" for first doc, or 4 chars from previous hash |
| InvoiceDate | Your invoice data |
| SystemEntryDate | Your invoice data (creation timestamp) |
| GrossTotal | Your invoice calculation |
| All other fields | Your database |

### Step 6: Printed Document Requirements (App-Side)

AT requires specific elements on printed invoices:

```
┌─────────────────────────────────────────────────────────────┐
│                     FATURA Nº FT FT2025/000001              │ ← Same as SAF-T InvoiceNo
│                                                             │
│  ATCUD: FTAA0001-000001                                     │ ← Above QR code
│  ┌──────────┐                                               │
│  │ QR CODE  │  Processado por programa certificado nº XXXX  │
│  │          │  ABCD                                         │ ← hash_chars below QR
│  └──────────┘                                               │
│                                                             │
│  ... invoice content ...                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**App responsibility**: Design PDF templates with these elements.

### Step 7: Real-time Communication (Optional, Using libefaturas)

For real-time invoice reporting to AT:

```python
from libefaturas import EFaturasClient

client = EFaturasClient(...)

result = client.register_invoice(
    efatura_md_version="0.0.1",
    audit_file_version="1.04_01",
    tax_registration_number=company_config["vat"].replace("PT", ""),
    tax_entity="Global",
    software_certificate_number=company_config["software_cert_number"],
    invoice_data={
        "InvoiceNo": saft_invoice_no,
        "ATCUD": atcud,
        "InvoiceDate": invoice["date"],
        "InvoiceType": sequence["document_type"],
        # ... all required fields per AT manual
    },
    canal_registo={"Sistema": "MyApp", "Versao": "1.0.0"},
)

if not result.ok:
    # Handle error - invoice may need retry later
    log_error(f"AT communication failed: {result.code} - {result.message}")
```

---

## Checklist: What You Must Build

### Database Schema
- [ ] Companies table with AT credentials and certificate paths
- [ ] Document sequences table (per company, per document type)
- [ ] Invoices table with hash, previous_hash, atcud fields
- [ ] Customers table with VAT, country, address
- [ ] Products table with code, description, unit
- [ ] Tax codes table with AT tax type mappings

### Business Logic
- [ ] Atomic sequence number generation (no gaps)
- [ ] Previous hash lookup for chain continuity
- [ ] Tax calculation with correct AT rates
- [ ] Credit note linking to original invoice
- [ ] Document cancellation workflow
- [ ] Multi-company support

### User Interface
- [ ] Invoice creation form
- [ ] Series registration wizard
- [ ] SAF-T export wizard with date range
- [ ] Document printing with AT-required elements
- [ ] Error handling for AT communication failures

### SAF-T Export
- [ ] Header section (company info, date range)
- [ ] MasterFiles (customers, products, taxes)
- [ ] SalesInvoices section
- [ ] MovementOfGoods section (if applicable)
- [ ] WorkingDocuments section (quotes, pro-formas)
- [ ] Payments section (receipts)
- [ ] Windows-1252 encoding
- [ ] XML schema validation

### Testing
- [ ] Hash chain verification (sequential documents)
- [ ] QR code scanning verification
- [ ] SAF-T validation against AT schema
- [ ] Series registration/finalization cycle
- [ ] Multi-user concurrent document creation

---

## Common Integration Mistakes

### 1. Gap in Document Numbers
**Problem**: Missing or duplicated numbers in sequence.
**Solution**: Use database transactions with row locking for sequence updates.

### 2. Wrong Hash Chain
**Problem**: Using wrong previous hash, breaking the chain.
**Solution**: Always query the most recent document by create_date DESC within same sequence.

### 3. Incorrect ATCUD Format
**Problem**: ATCUD not matching AT specification.
**Solution**: Use `format_atcud()` - format is `ValidationCode-PaddedNumber`.

### 4. Wrong Document Number on Print
**Problem**: Printed number differs from SAF-T InvoiceNo.
**Solution**: Store and use the same `format_invoice_no()` result everywhere.

### 5. Hash Before ATCUD Assignment
**Problem**: Trying to generate hash before sequence is registered with AT.
**Solution**: Ensure series has `at_state == "registered"` before creating documents.

### 6. SAF-T Encoding
**Problem**: Using UTF-8 instead of Windows-1252.
**Solution**: Always encode SAF-T as `Windows-1252` per AT specification.

---

## Reference: AT Document Types

| Type | Class | Description | Section |
|------|-------|-------------|---------|
| FT | SI | Fatura (Invoice) | SalesInvoices |
| FS | SI | Fatura Simplificada (Simplified Invoice) | SalesInvoices |
| FR | SI | Fatura-Recibo (Invoice-Receipt) | SalesInvoices |
| NC | SI | Nota de Crédito (Credit Note) | SalesInvoices |
| ND | SI | Nota de Débito (Debit Note) | SalesInvoices |
| GR | MG | Guia de Remessa (Delivery Note) | MovementOfGoods |
| GT | MG | Guia de Transporte (Transport Guide) | MovementOfGoods |
| GA | MG | Guia de Movimentação de Ativos (Asset Movement) | MovementOfGoods |
| GC | MG | Guia de Consignação (Consignment Guide) | MovementOfGoods |
| GD | MG | Guia de Devolução (Return Guide) | MovementOfGoods |
| OR | WD | Orçamento (Quote) | WorkingDocuments |
| PP | WD | Pro-Forma | WorkingDocuments |
| RC | PM | Recibo (Receipt) | Payments |

---

## Support

- **libefaturas issues**: https://github.com/glie/libefaturas/issues
- **AT documentation**: https://faturas.portaldasfinancas.gov.pt/documentos.action
- **SAF-T PT schema**: Portaria 302/2016 (version 1.04_01)
