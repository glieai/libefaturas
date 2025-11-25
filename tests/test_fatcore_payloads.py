from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import unittest
import xml.etree.ElementTree as ET

from libefaturas.faturas import (
    ChannelInfo,
    DeleteInvoiceInput,
    FaturasService,
    RegisterInvoiceInput,
)
from libefaturas.fatcore_payloads import (
    DateRange,
    DocumentTotals,
    InvoiceData,
    InvoiceLineSummary,
    InvoiceStatus,
    PayloadValidationError,
    Tax,
)


class DummyClient:
    def build_envelope_xml(self, body_xml: str) -> str:
        return (
            '<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">'
            f"{body_xml}"
            "</S:Envelope>"
        )


class PayloadValidationTests(unittest.TestCase):
    def _sample_invoice(self) -> InvoiceData:
        return InvoiceData(
            invoice_no="FT A/1",
            atcud="0",
            invoice_date=date(2024, 1, 1),
            invoice_type="FT",
            self_billing_indicator=0,
            customer_tax_id="999999990",
            customer_tax_id_country="PT",
            document_status=InvoiceStatus(
                invoice_status="N",
                invoice_status_date=datetime(2024, 1, 1, 12, 0, 0),
            ),
            hash_characters="ABCD",
            cash_vat_scheme_indicator=0,
            paperless_indicator=1,
            system_entry_date=datetime(2024, 1, 1, 12, 0, 0),
            line_summary=[
                InvoiceLineSummary(
                    tax_point_date=date(2024, 1, 1),
                    debit_credit_indicator="D",
                    total_tax_base=Decimal("100.00"),
                    tax=Tax(
                        tax_type="IVA",
                        tax_country_region="PT",
                        tax_code="NOR",
                        tax_percentage=Decimal("23.00"),
                    ),
                )
            ],
            document_totals=DocumentTotals(
                tax_payable=Decimal("23.00"),
                net_total=Decimal("100.00"),
                gross_total=Decimal("123.00"),
            ),
        )

    def test_invoice_payload_serializes_to_xml(self) -> None:
        data = self._sample_invoice()
        payload = RegisterInvoiceInput(
            efatura_md_version="0.0.1",
            audit_file_version="1.04_01",
            tax_registration_number="599999990",
            tax_entity="Global",
            software_certificate_number=9999,
            invoice_data=data,
            canal_registo=ChannelInfo(sistema="Tests", versao="1.0"),
        ).to_payload()
        service = FaturasService(DummyClient())
        body = service._build_body("RegisterInvoiceRequest", payload)
        envelope = DummyClient().build_envelope_xml(body)
        root = ET.fromstring(envelope)
        ns = {"fat": "http://factemi.at.min_financas.pt/documents"}
        request = root.find(".//fat:RegisterInvoiceRequest", ns)
        self.assertIsNotNone(request)
        invoice_no = request.findtext(".//fat:InvoiceNo", namespaces=ns)
        tax_code = request.findtext(".//fat:Tax/fat:TaxCode", namespaces=ns)
        self.assertEqual(invoice_no, "FT A/1")
        self.assertEqual(tax_code, "NOR")

    def test_tax_requires_percentage_or_amount(self) -> None:
        with self.assertRaises(PayloadValidationError):
            Tax(
                tax_type="IVA",
                tax_country_region="PT",
                tax_code="NOR",
                tax_percentage=Decimal("23.00"),
                total_tax_amount=Decimal("10.00"),
            )

    def test_date_range_validates_order(self) -> None:
        with self.assertRaises(PayloadValidationError):
            DateRange(start_date=date(2024, 2, 1), end_date=date(2024, 1, 1))

    def test_delete_invoice_requires_filter(self) -> None:
        with self.assertRaises(PayloadValidationError):
            DeleteInvoiceInput(
                efatura_md_version="0.0.1",
                tax_registration_number="599999990",
                reason="razão suficientemente longa",
            )


if __name__ == "__main__":
    unittest.main()
