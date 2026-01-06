"""Portuguese Tax Authority (AT) utility functions.

This module provides reusable utilities for Portuguese invoicing compliance:
- QR Code payload generation
- Hash character extraction
- ATCUD formatting
- Document number formatting
- Tax rate classification
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Sequence

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


def q2(value: Any) -> str:
    """Format a decimal value with 2 decimal places.

    Args:
        value: Numeric value (int, float, Decimal, str)

    Returns:
        String with 2 decimal places, dot as separator (e.g., "123.45")
    """
    quantized = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(quantized, "f")


def q6(value: Any) -> str:
    """Format a decimal value with 6 decimal places (for UnitPrice in SAF-T).

    Args:
        value: Numeric value (int, float, Decimal, str)

    Returns:
        String with 6 decimal places, dot as separator (e.g., "123.456789")
    """
    quantized = Decimal(str(value or 0)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return format(quantized, "f")


def extract_hash_chars(digest: str) -> str:
    """Extract the 4 hash characters required for QR code and printed documents.

    Per AT rules, these are the 1st, 11th, 21st, and 31st characters (1-indexed)
    of the Base64-encoded hash, which corresponds to indices 0, 10, 20, 30.

    Args:
        digest: Base64-encoded hash string (from document signing)

    Returns:
        4-character string, or "AAAA" if hash is invalid/too short
    """
    if not digest or len(digest) < 31:
        return "AAAA"
    indices = [0, 10, 20, 30]
    return "".join(digest[i] for i in indices)


def extract_hash_control(digest: str) -> str:
    """Extract HashControl value for SAF-T (first 70 characters of hash).

    Args:
        digest: Base64-encoded hash string

    Returns:
        First 70 characters of hash, or "0" if empty
    """
    if not digest:
        return "0"
    return digest[:70]


def format_invoice_no(
    doc_type: str,
    series_code: str,
    sequence_number: int,
    padding: int = 6,
) -> str:
    """Format a document number according to SAF-T InvoiceNo format.

    The format is: "{DocType} {SeriesCode}/{PaddedNumber}"
    Example: "FT FT2025/000001"

    Args:
        doc_type: Document type code (FT, FS, NC, ND, etc.)
        series_code: Series identifier (e.g., "FT2025", "A")
        sequence_number: Sequential document number
        padding: Number of digits to pad the sequence (default: 6)

    Returns:
        Formatted invoice number string
    """
    seq_str = str(sequence_number).zfill(padding)
    return f"{doc_type} {series_code}/{seq_str}"


def format_atcud(validation_code: str, sequence_number: int, padding: int = 6) -> str:
    """Format ATCUD (Código Único de Documento).

    ATCUD format: "{ValidationCode}-{SequenceNumber}"
    Example: "FTAA0001-000001"

    Args:
        validation_code: AT validation code for the series (8 characters)
        sequence_number: Sequential document number
        padding: Number of digits to pad the sequence (default: 6)

    Returns:
        Formatted ATCUD string
    """
    seq_str = str(sequence_number).zfill(padding)
    return f"{validation_code}-{seq_str}"


def classify_tax_rate(rate: Decimal) -> str:
    """Classify a VAT rate into AT tax code categories.

    Portugal has three VAT rate tiers:
    - NOR (Normal): 23% mainland, 22% Madeira, 16% Azores
    - INT (Intermediate): 13% mainland, 12% Madeira, 9% Azores
    - RED (Reduced): 6% mainland, 5% Madeira, 4% Azores
    - ISE (Exempt): 0%

    Args:
        rate: Tax percentage as Decimal (e.g., Decimal("23"))

    Returns:
        Tax code: "ISE", "RED", "INT", or "NOR"
    """
    if rate == 0:
        return "ISE"
    elif rate <= Decimal("6.5"):
        return "RED"
    elif rate <= Decimal("13.5"):
        return "INT"
    else:
        return "NOR"


@dataclass
class TaxTotals:
    """Tax totals broken down by rate category."""

    ise_base: Decimal = Decimal("0.00")  # Exempt base
    red_base: Decimal = Decimal("0.00")  # Reduced rate base
    red_tax: Decimal = Decimal("0.00")   # Reduced rate tax
    int_base: Decimal = Decimal("0.00")  # Intermediate rate base
    int_tax: Decimal = Decimal("0.00")   # Intermediate rate tax
    nor_base: Decimal = Decimal("0.00")  # Normal rate base
    nor_tax: Decimal = Decimal("0.00")   # Normal rate tax


def calculate_tax_totals(
    lines: Sequence[Dict[str, Any]],
    base_field: str = "price_subtotal",
    tax_field: str = "tax_rate",
) -> TaxTotals:
    """Calculate tax totals by rate category from invoice lines.

    Args:
        lines: Sequence of line dicts with base amount and tax rate
        base_field: Key for the base amount in each line dict
        tax_field: Key for the tax percentage in each line dict

    Returns:
        TaxTotals dataclass with amounts by category
    """
    totals = TaxTotals()

    for line in lines:
        base = Decimal(str(line.get(base_field, 0)))
        rate = Decimal(str(line.get(tax_field, 0)))
        category = classify_tax_rate(rate)

        if category == "ISE":
            totals.ise_base += base
        elif category == "RED":
            totals.red_base += base
            totals.red_tax += base * (rate / Decimal("100"))
        elif category == "INT":
            totals.int_base += base
            totals.int_tax += base * (rate / Decimal("100"))
        else:  # NOR
            totals.nor_base += base
            totals.nor_tax += base * (rate / Decimal("100"))

    return totals


def build_qr_payload(
    *,
    issuer_vat: str,
    customer_vat: str,
    customer_country: str,
    doc_type: str,
    doc_status: str,
    doc_date: date | datetime | str,
    doc_no: str,
    atcud: str,
    fiscal_region: str = "PT",
    tax_totals: Optional[TaxTotals] = None,
    total_tax: Decimal | str = Decimal("0"),
    total_gross: Decimal | str = Decimal("0"),
    hash_chars: str = "AAAA",
    cert_number: int = 0,
    iban: Optional[str] = None,
    mb_entity: Optional[str] = None,
    mb_reference: Optional[str] = None,
    include_field_markers: bool = True,
) -> str:
    """Build the QR code payload string according to AT specifications.

    The QR code contains fields A through S with specific data about the document.
    Field markers (A:, B:, etc.) can be included or omitted based on configuration.

    Args:
        issuer_vat: Issuer VAT number (without country prefix)
        customer_vat: Customer VAT number (or "999999990" for final consumer)
        customer_country: Customer country ISO code (e.g., "PT")
        doc_type: Document type (FT, FS, NC, ND, FR, etc.)
        doc_status: Document status (N=Normal, A=Cancelled, F=Billed)
        doc_date: Document date (will be formatted as YYYYMMDD)
        doc_no: Document identification (SAF-T InvoiceNo format)
        atcud: ATCUD code
        fiscal_region: Fiscal region (PT, PT-AC, PT-MA)
        tax_totals: Pre-calculated tax totals by category
        total_tax: Total tax amount
        total_gross: Total gross amount (including tax)
        hash_chars: 4 characters extracted from document hash
        cert_number: Software certificate number
        iban: Optional IBAN for payment
        mb_entity: Optional MB (Multibanco) entity code
        mb_reference: Optional MB reference

    Returns:
        QR code payload string with fields separated by "*"
    """
    # Format date
    if isinstance(doc_date, str):
        date_str = doc_date.replace("-", "")[:8]
    elif isinstance(doc_date, datetime):
        date_str = doc_date.strftime("%Y%m%d")
    else:
        date_str = doc_date.strftime("%Y%m%d")

    # Build fields list
    fields: List[str] = [
        f"A:{issuer_vat}" if include_field_markers else issuer_vat,
        f"B:{customer_vat}" if include_field_markers else customer_vat,
        f"C:{customer_country}" if include_field_markers else customer_country,
        f"D:{doc_type}" if include_field_markers else doc_type,
        f"E:{doc_status}" if include_field_markers else doc_status,
        f"F:{date_str}" if include_field_markers else date_str,
        f"G:{doc_no}" if include_field_markers else doc_no,
        f"H:{atcud}" if include_field_markers else atcud,
        f"I1:{fiscal_region}" if include_field_markers else fiscal_region,
    ]

    # Tax breakdown fields (I2-I8) - only include if non-zero
    if tax_totals:
        if tax_totals.ise_base != 0:
            val = q2(tax_totals.ise_base)
            fields.append(f"I2:{val}" if include_field_markers else val)
        if tax_totals.red_base != 0:
            val = q2(tax_totals.red_base)
            fields.append(f"I3:{val}" if include_field_markers else val)
        if tax_totals.red_tax != 0:
            val = q2(tax_totals.red_tax)
            fields.append(f"I4:{val}" if include_field_markers else val)
        if tax_totals.int_base != 0:
            val = q2(tax_totals.int_base)
            fields.append(f"I5:{val}" if include_field_markers else val)
        if tax_totals.int_tax != 0:
            val = q2(tax_totals.int_tax)
            fields.append(f"I6:{val}" if include_field_markers else val)
        if tax_totals.nor_base != 0:
            val = q2(tax_totals.nor_base)
            fields.append(f"I7:{val}" if include_field_markers else val)
        if tax_totals.nor_tax != 0:
            val = q2(tax_totals.nor_tax)
            fields.append(f"I8:{val}" if include_field_markers else val)

    # Totals
    fields.append(f"N:{q2(total_tax)}" if include_field_markers else q2(total_tax))
    fields.append(f"O:{q2(total_gross)}" if include_field_markers else q2(total_gross))
    fields.append(f"Q:{hash_chars}" if include_field_markers else hash_chars)
    fields.append(f"R:{cert_number}" if include_field_markers else str(cert_number))

    # Optional payment info
    if iban:
        iban_clean = iban.replace(" ", "")
        fields.append(f"S:IBAN;{iban_clean}" if include_field_markers else f"IBAN;{iban_clean}")
    if mb_entity and mb_reference:
        fields.append(f"S:MB;{mb_entity};{mb_reference}" if include_field_markers else f"MB;{mb_entity};{mb_reference}")

    return "*".join(fields)


def generate_qr_png(payload: str, box_size: int = 10, border: int = 4) -> bytes:
    """Generate a QR code PNG image from payload.

    Args:
        payload: QR code payload string (from build_qr_payload)
        box_size: Size of each box in pixels
        border: Border size in boxes

    Returns:
        PNG image as bytes

    Raises:
        ImportError: If qrcode library is not installed
    """
    if not HAS_QRCODE:
        raise ImportError(
            "qrcode library is required for QR code generation. "
            "Install with: pip install qrcode[pil]"
        )

    qr = qrcode.QRCode(
        version=None,  # Auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# Valid document types per SAF-T section
VALID_SALES_INVOICE_TYPES = frozenset({
    "FT", "FS", "FR", "ND", "NC", "VD", "TV", "TD",
    "AA", "DA", "RP", "RE", "CS", "LD", "RA",
})

VALID_MOVEMENT_OF_GOODS_TYPES = frozenset({
    "GR", "GT", "GA", "GC", "GD",
})

VALID_WORKING_DOCUMENT_TYPES = frozenset({
    "OR", "PP", "FC", "PO", "NE", "OU",
})

VALID_PAYMENT_TYPES = frozenset({
    "RC", "RG",
})


def get_document_section(doc_type: str) -> str:
    """Determine which SAF-T section a document type belongs to.

    Args:
        doc_type: Document type code

    Returns:
        Section name: "SalesInvoices", "MovementOfGoods",
                     "WorkingDocuments", "Payments", or "Unknown"
    """
    if doc_type in VALID_SALES_INVOICE_TYPES:
        return "SalesInvoices"
    elif doc_type in VALID_MOVEMENT_OF_GOODS_TYPES:
        return "MovementOfGoods"
    elif doc_type in VALID_WORKING_DOCUMENT_TYPES:
        return "WorkingDocuments"
    elif doc_type in VALID_PAYMENT_TYPES:
        return "Payments"
    else:
        return "Unknown"


# Portuguese tax rates by region
PT_TAX_RATES = {
    "PT": {
        "NOR": Decimal("23"),
        "INT": Decimal("13"),
        "RED": Decimal("6"),
    },
    "PT-MA": {  # Madeira
        "NOR": Decimal("22"),
        "INT": Decimal("12"),
        "RED": Decimal("5"),
    },
    "PT-AC": {  # Azores
        "NOR": Decimal("16"),
        "INT": Decimal("9"),
        "RED": Decimal("4"),
    },
}


def get_tax_rate(region: str, code: str) -> Decimal:
    """Get the tax rate for a region and tax code.

    Args:
        region: Fiscal region (PT, PT-MA, PT-AC)
        code: Tax code (NOR, INT, RED)

    Returns:
        Tax percentage as Decimal

    Raises:
        ValueError: If region or code is invalid
    """
    if region not in PT_TAX_RATES:
        raise ValueError(f"Invalid region: {region}. Must be one of: {list(PT_TAX_RATES.keys())}")
    rates = PT_TAX_RATES[region]
    if code not in rates:
        raise ValueError(f"Invalid tax code: {code}. Must be one of: {list(rates.keys())}")
    return rates[code]
