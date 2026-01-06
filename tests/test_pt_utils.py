"""Tests for Portuguese Tax Authority utility functions."""

from datetime import date
from decimal import Decimal

import pytest

from libefaturas.pt_utils import (
    PT_TAX_RATES,
    TaxTotals,
    VALID_MOVEMENT_OF_GOODS_TYPES,
    VALID_SALES_INVOICE_TYPES,
    VALID_WORKING_DOCUMENT_TYPES,
    build_qr_payload,
    calculate_tax_totals,
    classify_tax_rate,
    extract_hash_chars,
    extract_hash_control,
    format_atcud,
    format_invoice_no,
    get_document_section,
    get_tax_rate,
    q2,
    q6,
)


class TestDecimalFormatting:
    """Tests for decimal formatting functions."""

    def test_q2_basic(self):
        """Test basic 2-decimal formatting."""
        assert q2(100) == "100.00"
        assert q2(100.5) == "100.50"
        assert q2(100.555) == "100.56"  # Rounds up
        assert q2(100.554) == "100.55"  # Rounds down

    def test_q2_decimal(self):
        """Test q2 with Decimal input."""
        assert q2(Decimal("123.456")) == "123.46"
        assert q2(Decimal("0.005")) == "0.01"

    def test_q2_string(self):
        """Test q2 with string input."""
        assert q2("99.999") == "100.00"

    def test_q2_none_or_zero(self):
        """Test q2 with None or zero."""
        assert q2(None) == "0.00"
        assert q2(0) == "0.00"

    def test_q6_basic(self):
        """Test 6-decimal formatting for UnitPrice."""
        assert q6(100) == "100.000000"
        assert q6(0.123456) == "0.123456"
        assert q6(0.1234567) == "0.123457"  # Rounds


class TestHashExtraction:
    """Tests for hash character extraction."""

    def test_extract_hash_chars_valid(self):
        """Test extracting 4 characters from valid hash."""
        # Simulated base64 hash (at least 31 chars)
        hash_value = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
        result = extract_hash_chars(hash_value)
        # Positions 0, 10, 20, 30 -> A, K, U, e
        assert result == "AKUe"

    def test_extract_hash_chars_short_hash(self):
        """Test fallback when hash is too short."""
        assert extract_hash_chars("short") == "AAAA"
        assert extract_hash_chars("") == "AAAA"
        assert extract_hash_chars(None) == "AAAA"

    def test_extract_hash_chars_exact_31(self):
        """Test with exactly 31 characters."""
        hash_value = "0123456789012345678901234567890"  # 31 chars
        result = extract_hash_chars(hash_value)
        assert result == "0000"

    def test_extract_hash_control_valid(self):
        """Test extracting first 70 characters for HashControl."""
        long_hash = "A" * 100
        assert extract_hash_control(long_hash) == "A" * 70

    def test_extract_hash_control_short(self):
        """Test HashControl with short hash."""
        assert extract_hash_control("ABC") == "ABC"
        assert extract_hash_control("") == "0"
        assert extract_hash_control(None) == "0"


class TestDocumentFormatting:
    """Tests for document number and ATCUD formatting."""

    def test_format_invoice_no_basic(self):
        """Test basic invoice number formatting."""
        result = format_invoice_no("FT", "FT2025", 1)
        assert result == "FT FT2025/000001"

    def test_format_invoice_no_custom_padding(self):
        """Test with custom padding."""
        result = format_invoice_no("NC", "A", 123, padding=8)
        assert result == "NC A/00000123"

    def test_format_invoice_no_large_number(self):
        """Test with number larger than padding."""
        result = format_invoice_no("FT", "B", 1234567, padding=6)
        assert result == "FT B/1234567"

    def test_format_atcud_basic(self):
        """Test basic ATCUD formatting."""
        result = format_atcud("FTAA0001", 1)
        assert result == "FTAA0001-000001"

    def test_format_atcud_custom_padding(self):
        """Test ATCUD with custom padding."""
        result = format_atcud("NCBB2222", 999, padding=8)
        assert result == "NCBB2222-00000999"


class TestTaxClassification:
    """Tests for tax rate classification."""

    def test_classify_exempt(self):
        """Test exempt classification."""
        assert classify_tax_rate(Decimal("0")) == "ISE"

    def test_classify_reduced(self):
        """Test reduced rate classification."""
        assert classify_tax_rate(Decimal("4")) == "RED"
        assert classify_tax_rate(Decimal("5")) == "RED"
        assert classify_tax_rate(Decimal("6")) == "RED"
        assert classify_tax_rate(Decimal("6.5")) == "RED"

    def test_classify_intermediate(self):
        """Test intermediate rate classification."""
        assert classify_tax_rate(Decimal("9")) == "INT"
        assert classify_tax_rate(Decimal("12")) == "INT"
        assert classify_tax_rate(Decimal("13")) == "INT"
        assert classify_tax_rate(Decimal("13.5")) == "INT"

    def test_classify_normal(self):
        """Test normal rate classification."""
        assert classify_tax_rate(Decimal("16")) == "NOR"
        assert classify_tax_rate(Decimal("22")) == "NOR"
        assert classify_tax_rate(Decimal("23")) == "NOR"


class TestTaxRates:
    """Tests for regional tax rates."""

    def test_mainland_rates(self):
        """Test PT mainland rates."""
        assert get_tax_rate("PT", "NOR") == Decimal("23")
        assert get_tax_rate("PT", "INT") == Decimal("13")
        assert get_tax_rate("PT", "RED") == Decimal("6")

    def test_madeira_rates(self):
        """Test PT-MA (Madeira) rates."""
        assert get_tax_rate("PT-MA", "NOR") == Decimal("22")
        assert get_tax_rate("PT-MA", "INT") == Decimal("12")
        assert get_tax_rate("PT-MA", "RED") == Decimal("5")

    def test_azores_rates(self):
        """Test PT-AC (Azores) rates."""
        assert get_tax_rate("PT-AC", "NOR") == Decimal("16")
        assert get_tax_rate("PT-AC", "INT") == Decimal("9")
        assert get_tax_rate("PT-AC", "RED") == Decimal("4")

    def test_invalid_region(self):
        """Test error for invalid region."""
        with pytest.raises(ValueError, match="Invalid region"):
            get_tax_rate("ES", "NOR")

    def test_invalid_code(self):
        """Test error for invalid tax code."""
        with pytest.raises(ValueError, match="Invalid tax code"):
            get_tax_rate("PT", "XXX")


class TestTaxTotals:
    """Tests for tax totals calculation."""

    def test_calculate_empty_lines(self):
        """Test with no lines."""
        result = calculate_tax_totals([])
        assert result.ise_base == Decimal("0.00")
        assert result.nor_base == Decimal("0.00")

    def test_calculate_single_normal_rate(self):
        """Test single line with normal rate."""
        lines = [{"price_subtotal": 100, "tax_rate": 23}]
        result = calculate_tax_totals(lines)
        assert result.nor_base == Decimal("100")
        assert result.nor_tax == Decimal("23")

    def test_calculate_mixed_rates(self):
        """Test lines with different rates."""
        lines = [
            {"price_subtotal": 100, "tax_rate": 23},  # Normal
            {"price_subtotal": 50, "tax_rate": 13},   # Intermediate
            {"price_subtotal": 25, "tax_rate": 6},    # Reduced
            {"price_subtotal": 10, "tax_rate": 0},    # Exempt
        ]
        result = calculate_tax_totals(lines)
        assert result.nor_base == Decimal("100")
        assert result.nor_tax == Decimal("23")
        assert result.int_base == Decimal("50")
        assert result.int_tax == Decimal("6.5")
        assert result.red_base == Decimal("25")
        assert result.red_tax == Decimal("1.5")
        assert result.ise_base == Decimal("10")


class TestDocumentSections:
    """Tests for document type to SAF-T section mapping."""

    def test_sales_invoice_types(self):
        """Test all valid sales invoice types."""
        for doc_type in VALID_SALES_INVOICE_TYPES:
            assert get_document_section(doc_type) == "SalesInvoices"

    def test_movement_of_goods_types(self):
        """Test all valid movement of goods types."""
        for doc_type in VALID_MOVEMENT_OF_GOODS_TYPES:
            assert get_document_section(doc_type) == "MovementOfGoods"

    def test_working_document_types(self):
        """Test all valid working document types."""
        for doc_type in VALID_WORKING_DOCUMENT_TYPES:
            assert get_document_section(doc_type) == "WorkingDocuments"

    def test_unknown_type(self):
        """Test unknown document type."""
        assert get_document_section("XX") == "Unknown"


class TestQRPayload:
    """Tests for QR code payload building."""

    def test_basic_payload(self):
        """Test basic QR payload generation."""
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
        assert "A:123456789" in payload
        assert "B:999999990" in payload
        assert "C:PT" in payload
        assert "D:FT" in payload
        assert "E:N" in payload
        assert "F:20250115" in payload
        assert "G:FT FT2025/000001" in payload
        assert "H:FTAA0001-000001" in payload
        assert "N:23.00" in payload
        assert "O:123.00" in payload
        assert "Q:ABCD" in payload
        assert "R:9999" in payload

    def test_payload_without_markers(self):
        """Test payload without field markers."""
        payload = build_qr_payload(
            issuer_vat="123456789",
            customer_vat="999999990",
            customer_country="PT",
            doc_type="FT",
            doc_status="N",
            doc_date="2025-01-15",
            doc_no="FT A/1",
            atcud="0",
            total_tax=0,
            total_gross=100,
            hash_chars="AAAA",
            cert_number=0,
            include_field_markers=False,
        )
        assert "A:" not in payload
        assert "123456789*999999990*PT" in payload

    def test_payload_with_tax_totals(self):
        """Test payload with tax breakdown."""
        totals = TaxTotals(
            nor_base=Decimal("100"),
            nor_tax=Decimal("23"),
            ise_base=Decimal("50"),
        )
        payload = build_qr_payload(
            issuer_vat="123456789",
            customer_vat="999999990",
            customer_country="PT",
            doc_type="FT",
            doc_status="N",
            doc_date=date(2025, 1, 15),
            doc_no="FT A/1",
            atcud="0",
            tax_totals=totals,
            total_tax=Decimal("23"),
            total_gross=Decimal("173"),
            hash_chars="AAAA",
            cert_number=0,
        )
        assert "I2:50.00" in payload  # Exempt base
        assert "I7:100.00" in payload  # Normal base
        assert "I8:23.00" in payload   # Normal tax

    def test_payload_with_payment_info(self):
        """Test payload with IBAN and MB info."""
        payload = build_qr_payload(
            issuer_vat="123456789",
            customer_vat="999999990",
            customer_country="PT",
            doc_type="FT",
            doc_status="N",
            doc_date=date(2025, 1, 15),
            doc_no="FT A/1",
            atcud="0",
            total_tax=0,
            total_gross=100,
            hash_chars="AAAA",
            cert_number=0,
            iban="PT50 0000 0000 1234 5678 9012 3",
            mb_entity="12345",
            mb_reference="123 456 789",
        )
        assert "S:IBAN;PT50000000001234567890123" in payload
        assert "S:MB;12345;123 456 789" in payload
