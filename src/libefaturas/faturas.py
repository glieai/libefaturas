"""Interface de alto nível para o Fatcorews (faturas/obras/pagamentos)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence
import xml.etree.ElementTree as ET
import re

from .client import _WSClient


__all__ = [
    "ChannelInfo",
    "DateRange",
    "Tax",
    "WithholdingTax",
    "DocumentTotals",
    "InvoiceStatus",
    "NewInvoiceStatus",
    "InvoiceLineSummary",
    "InvoiceHeader",
    "InvoiceData",
    "WorkStatus",
    "NewWorkStatus",
    "WorkLineSummary",
    "WorkHeader",
    "WorkData",
    "PaymentStatus",
    "NewPaymentStatus",
    "PaymentLineSummary",
    "PaymentHeader",
    "PaymentData",
    "OrderReference",
    "SourceDocumentID",
    "PayloadValidationError",
    "RegisterInvoiceInput",
    "ChangeInvoiceStatusInput",
    "DeleteInvoiceInput",
    "RegisterWorkInput",
    "ChangeWorkStatusInput",
    "DeleteWorkInput",
    "RegisterPaymentInput",
    "ChangePaymentStatusInput",
    "DeletePaymentInput",
    "OperationResponse",
    "FaturasError",
    "FaturasService",
]


NamespacePayload = Mapping[str, Any]


class PayloadValidationError(ValueError):
    """Erro de validação de payload antes do envio para o WSDL."""


_VAT_MIN = 100000000
_VAT_MAX = 999999999
_TAX_CODE_RE = re.compile(r"RED|INT|NOR|ISE|OUT|([a-zA-Z0-9.])*|NS|NA")
_COUNTRY_RE = re.compile(r"[A-Z]{2}|PT-MA|PT-AC")
_INVOICE_NO_RE = re.compile(r"[^ ]+ [^/^ ]+/[0-9]+")
_EAC_RE = re.compile(r"\d{5}")
_HASH_CHARS_RE = re.compile(r"0|[^^]{4}")
_TAX_EXEMPTION_RE = re.compile(r"(M[0-9]{2})+")
_AUDIT_FILE_VERSIONS = {
    "1.04_01",
    "1.03_01",
    "1.02_01",
    "1.01_01",
    "1.00_01",
    "inexistente",
}
_INVOICE_TYPES = {"FT", "NC", "ND", "FS", "FR", "RP", "RE", "CS", "LD", "RA"}
_WORK_TYPES = {"CM", "CC", "FC", "FO", "NE", "OU", "OR", "PF", "RP", "RE", "CS", "LD", "RA"}
_PAYMENT_TYPES = {"RC"}
_DEBIT_CREDIT = {"D", "C"}
_MONETARY_MIN = Decimal("0.00")
_MONETARY_MAX = Decimal("9999999999999.99")
_PERCENTAGE_MIN = Decimal("0.00")
_PERCENTAGE_MAX = Decimal("100.00")


def _ensure_str(
    value: Any,
    field: str,
    *,
    min_len: int = 1,
    max_len: Optional[int] = None,
    pattern: Optional[re.Pattern[str]] = None,
    upper: bool = False,
) -> str:
    if not isinstance(value, str):
        raise PayloadValidationError(f"{field} deve ser texto.")
    cleaned = value.strip()
    if len(cleaned) < min_len:
        raise PayloadValidationError(f"{field} deve ter pelo menos {min_len} caracteres.")
    if max_len is not None and len(cleaned) > max_len:
        raise PayloadValidationError(f"{field} deve ter no máximo {max_len} caracteres.")
    if pattern and not pattern.fullmatch(cleaned):
        raise PayloadValidationError(f"{field} não cumpre o formato esperado.")
    return cleaned.upper() if upper else cleaned


def _ensure_int(value: Any, field: str, *, min_value: Optional[int] = None, max_digits: Optional[int] = None) -> int:
    if isinstance(value, bool) or value is None:
        raise PayloadValidationError(f"{field} deve ser inteiro.")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise PayloadValidationError(f"{field} deve ser inteiro.") from exc
    if min_value is not None and number < min_value:
        raise PayloadValidationError(f"{field} deve ser >= {min_value}.")
    if max_digits is not None and len(str(abs(number))) > max_digits:
        raise PayloadValidationError(f"{field} deve ter no máximo {max_digits} dígitos.")
    return number


def _ensure_indicator(value: Any, field: str, allowed: set[int]) -> int:
    number = _ensure_int(value, field)
    if number not in allowed:
        allowed_txt = ", ".join(str(v) for v in sorted(allowed))
        raise PayloadValidationError(f"{field} deve ser um dos {allowed_txt}.")
    return number


def _ensure_decimal(
    value: Any,
    field: str,
    *,
    min_value: Optional[Decimal] = None,
    max_value: Optional[Decimal] = None,
) -> Decimal:
    try:
        dec_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PayloadValidationError(f"{field} deve ser um decimal válido.") from exc
    if min_value is not None and dec_value < min_value:
        raise PayloadValidationError(f"{field} deve ser >= {min_value}.")
    if max_value is not None and dec_value > max_value:
        raise PayloadValidationError(f"{field} deve ser <= {max_value}.")
    return dec_value


def _ensure_date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise PayloadValidationError(f"{field} deve ser uma data ISO (AAAA-MM-DD).") from exc
    raise PayloadValidationError(f"{field} deve ser data.")


def _ensure_datetime(value: Any, field: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            pass
    raise PayloadValidationError(f"{field} deve ser datetime (ISO 8601).")


def _ensure_sequence(value: Any, field: str) -> Sequence[Any]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return value
    raise PayloadValidationError(f"{field} deve ser uma lista.")


def _coerce_dataclass(value: Any, cls: type, field: str):
    if isinstance(value, cls):
        return value
    if isinstance(value, Mapping):
        try:
            candidate_fields = [item.name for item in fields(cls) if item.init]
        except TypeError:
            candidate_fields = []
        if candidate_fields and any(key in value for key in candidate_fields):
            try:
                kwargs = {name: value.get(name) for name in candidate_fields}
                return cls(**kwargs)
            except PayloadValidationError:
                raise
            except Exception:
                pass
        return cls.from_mapping(value)
    raise PayloadValidationError(f"{field} deve ser {cls.__name__} ou mapping.")


def _coerce_list(values: Any, cls: type, field: str, *, allow_empty: bool = False) -> list:
    seq = _ensure_sequence(values, field)
    result = []
    for idx, item in enumerate(seq):
        result.append(_coerce_dataclass(item, cls, f"{field}[{idx}]"))
    if not result and not allow_empty:
        raise PayloadValidationError(f"{field} deve ter pelo menos 1 elemento.")
    return result


@dataclass
class ChannelInfo:
    sistema: str
    versao: Optional[str] = None

    def __post_init__(self) -> None:
        self.sistema = _ensure_str(self.sistema, "Sistema", min_len=1, max_len=100)
        if self.versao is not None:
            self.versao = _ensure_str(self.versao, "Versao", min_len=1, max_len=100)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ChannelInfo":
        return cls(
            sistema=data.get("Sistema") or data.get("sistema"),
            versao=data.get("Versao") or data.get("versao"),
        )

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"Sistema": self.sistema}
        if self.versao:
            payload["Versao"] = self.versao
        return payload


@dataclass
class DateRange:
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        self.start_date = _ensure_date(self.start_date, "StartDate")
        self.end_date = _ensure_date(self.end_date, "EndDate")
        if self.start_date > self.end_date:
            raise PayloadValidationError("StartDate deve ser <= EndDate.")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "DateRange":
        return cls(
            start_date=data.get("StartDate"),
            end_date=data.get("EndDate"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {"StartDate": self.start_date, "EndDate": self.end_date}


@dataclass
class Tax:
    tax_type: str
    tax_country_region: str
    tax_code: str
    tax_percentage: Optional[Decimal] = None
    total_tax_amount: Optional[Decimal] = None

    def __post_init__(self) -> None:
        self.tax_type = _ensure_str(self.tax_type, "TaxType", upper=True)
        if self.tax_type not in {"IVA", "IS", "NS"}:
            raise PayloadValidationError("TaxType deve ser IVA, IS ou NS.")
        self.tax_country_region = _ensure_str(
            self.tax_country_region,
            "TaxCountryRegion",
            pattern=_COUNTRY_RE,
        )
        self.tax_code = _ensure_str(
            self.tax_code,
            "TaxCode",
            min_len=1,
            max_len=10,
            pattern=_TAX_CODE_RE,
            upper=True,
        )
        if (self.tax_percentage is None) == (self.total_tax_amount is None):
            raise PayloadValidationError("Indique TaxPercentage ou TotalTaxAmount (um e só um).")
        if self.tax_percentage is not None:
            self.tax_percentage = _ensure_decimal(
                self.tax_percentage,
                "TaxPercentage",
                min_value=_PERCENTAGE_MIN,
                max_value=_PERCENTAGE_MAX,
            )
        if self.total_tax_amount is not None:
            self.total_tax_amount = _ensure_decimal(
                self.total_tax_amount,
                "TotalTaxAmount",
                min_value=_MONETARY_MIN,
                max_value=_MONETARY_MAX,
            )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "Tax":
        return cls(
            tax_type=data.get("TaxType"),
            tax_country_region=data.get("TaxCountryRegion"),
            tax_code=data.get("TaxCode"),
            tax_percentage=data.get("TaxPercentage"),
            total_tax_amount=data.get("TotalTaxAmount"),
        )

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "TaxType": self.tax_type,
            "TaxCountryRegion": self.tax_country_region,
            "TaxCode": self.tax_code,
        }
        if self.tax_percentage is not None:
            payload["TaxPercentage"] = self.tax_percentage
        if self.total_tax_amount is not None:
            payload["TotalTaxAmount"] = self.total_tax_amount
        return payload


@dataclass
class WithholdingTax:
    withholding_tax_type: Optional[str]
    withholding_tax_amount: Decimal

    def __post_init__(self) -> None:
        if self.withholding_tax_type is not None:
            self.withholding_tax_type = _ensure_str(
                self.withholding_tax_type,
                "WithholdingTaxType",
                upper=True,
            )
            if self.withholding_tax_type not in {"IRS", "IRC", "IS"}:
                raise PayloadValidationError("WithholdingTaxType deve ser IRS, IRC ou IS.")
        self.withholding_tax_amount = _ensure_decimal(
            self.withholding_tax_amount,
            "WithholdingTaxAmount",
            min_value=_MONETARY_MIN,
            max_value=_MONETARY_MAX,
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "WithholdingTax":
        return cls(
            withholding_tax_type=data.get("WithholdingTaxType"),
            withholding_tax_amount=data.get("WithholdingTaxAmount"),
        )

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"WithholdingTaxAmount": self.withholding_tax_amount}
        if self.withholding_tax_type is not None:
            payload["WithholdingTaxType"] = self.withholding_tax_type
        return payload


@dataclass
class DocumentTotals:
    tax_payable: Decimal
    net_total: Decimal
    gross_total: Decimal

    def __post_init__(self) -> None:
        self.tax_payable = _ensure_decimal(
            self.tax_payable,
            "TaxPayable",
            min_value=_MONETARY_MIN,
            max_value=_MONETARY_MAX,
        )
        self.net_total = _ensure_decimal(
            self.net_total,
            "NetTotal",
            min_value=_MONETARY_MIN,
            max_value=_MONETARY_MAX,
        )
        self.gross_total = _ensure_decimal(
            self.gross_total,
            "GrossTotal",
            min_value=_MONETARY_MIN,
            max_value=_MONETARY_MAX,
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "DocumentTotals":
        return cls(
            tax_payable=data.get("TaxPayable"),
            net_total=data.get("NetTotal"),
            gross_total=data.get("GrossTotal"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "TaxPayable": self.tax_payable,
            "NetTotal": self.net_total,
            "GrossTotal": self.gross_total,
        }


@dataclass
class InvoiceStatus:
    invoice_status: str
    invoice_status_date: datetime

    def __post_init__(self) -> None:
        self.invoice_status = _ensure_str(
            self.invoice_status,
            "InvoiceStatus",
            upper=True,
        )
        if self.invoice_status not in {"N", "A", "F", "S"}:
            raise PayloadValidationError("InvoiceStatus deve ser N, A, F ou S.")
        self.invoice_status_date = _ensure_datetime(self.invoice_status_date, "InvoiceStatusDate")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "InvoiceStatus":
        return cls(
            invoice_status=data.get("InvoiceStatus"),
            invoice_status_date=data.get("InvoiceStatusDate"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "InvoiceStatus": self.invoice_status,
            "InvoiceStatusDate": self.invoice_status_date,
        }


@dataclass
class NewInvoiceStatus:
    invoice_status: str
    invoice_status_date: datetime

    def __post_init__(self) -> None:
        self.invoice_status = _ensure_str(
            self.invoice_status,
            "InvoiceStatus",
            upper=True,
        )
        if self.invoice_status not in {"N", "A", "F"}:
            raise PayloadValidationError("InvoiceStatus deve ser N, A ou F.")
        self.invoice_status_date = _ensure_datetime(self.invoice_status_date, "InvoiceStatusDate")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "NewInvoiceStatus":
        return cls(
            invoice_status=data.get("InvoiceStatus"),
            invoice_status_date=data.get("InvoiceStatusDate"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "InvoiceStatus": self.invoice_status,
            "InvoiceStatusDate": self.invoice_status_date,
        }


@dataclass
class WorkStatus:
    work_status: str
    work_status_date: datetime

    def __post_init__(self) -> None:
        self.work_status = _ensure_str(self.work_status, "WorkStatus", upper=True)
        if self.work_status not in {"N", "A", "F"}:
            raise PayloadValidationError("WorkStatus deve ser N, A ou F.")
        self.work_status_date = _ensure_datetime(self.work_status_date, "WorkStatusDate")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "WorkStatus":
        return cls(
            work_status=data.get("WorkStatus"),
            work_status_date=data.get("WorkStatusDate"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "WorkStatus": self.work_status,
            "WorkStatusDate": self.work_status_date,
        }


@dataclass
class NewWorkStatus:
    work_status: str
    work_status_date: datetime

    def __post_init__(self) -> None:
        self.work_status = _ensure_str(self.work_status, "WorkStatus", upper=True)
        if self.work_status not in {"N", "A", "F"}:
            raise PayloadValidationError("WorkStatus deve ser N, A ou F.")
        self.work_status_date = _ensure_datetime(self.work_status_date, "WorkStatusDate")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "NewWorkStatus":
        return cls(
            work_status=data.get("WorkStatus"),
            work_status_date=data.get("WorkStatusDate"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "WorkStatus": self.work_status,
            "WorkStatusDate": self.work_status_date,
        }


@dataclass
class PaymentStatus:
    payment_status: str
    payment_status_date: datetime

    def __post_init__(self) -> None:
        self.payment_status = _ensure_str(self.payment_status, "PaymentStatus", upper=True)
        if self.payment_status not in {"N", "A"}:
            raise PayloadValidationError("PaymentStatus deve ser N ou A.")
        self.payment_status_date = _ensure_datetime(self.payment_status_date, "PaymentStatusDate")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "PaymentStatus":
        return cls(
            payment_status=data.get("PaymentStatus"),
            payment_status_date=data.get("PaymentStatusDate"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "PaymentStatus": self.payment_status,
            "PaymentStatusDate": self.payment_status_date,
        }


@dataclass
class NewPaymentStatus:
    payment_status: str
    payment_status_date: datetime

    def __post_init__(self) -> None:
        self.payment_status = _ensure_str(self.payment_status, "PaymentStatus", upper=True)
        if self.payment_status not in {"N", "A"}:
            raise PayloadValidationError("PaymentStatus deve ser N ou A.")
        self.payment_status_date = _ensure_datetime(self.payment_status_date, "PaymentStatusDate")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "NewPaymentStatus":
        return cls(
            payment_status=data.get("PaymentStatus"),
            payment_status_date=data.get("PaymentStatusDate"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "PaymentStatus": self.payment_status,
            "PaymentStatusDate": self.payment_status_date,
        }


@dataclass
class OrderReference:
    originating_on: Optional[str] = None
    order_date: Optional[date] = None

    def __post_init__(self) -> None:
        if self.originating_on is not None:
            self.originating_on = _ensure_str(
                self.originating_on,
                "OriginatingON",
                min_len=1,
                max_len=60,
            )
        if self.order_date is not None:
            self.order_date = _ensure_date(self.order_date, "OrderDate")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "OrderReference":
        return cls(
            originating_on=data.get("OriginatingON"),
            order_date=data.get("OrderDate"),
        )

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.originating_on is not None:
            payload["OriginatingON"] = self.originating_on
        if self.order_date is not None:
            payload["OrderDate"] = self.order_date
        return payload


@dataclass
class SourceDocumentID:
    originating_on: str
    invoice_date: date

    def __post_init__(self) -> None:
        self.originating_on = _ensure_str(
            self.originating_on,
            "OriginatingON",
            min_len=1,
            max_len=60,
        )
        self.invoice_date = _ensure_date(self.invoice_date, "InvoiceDate")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "SourceDocumentID":
        return cls(
            originating_on=data.get("OriginatingON"),
            invoice_date=data.get("InvoiceDate"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "OriginatingON": self.originating_on,
            "InvoiceDate": self.invoice_date,
        }


@dataclass
class InvoiceLineSummary:
    tax_point_date: date
    debit_credit_indicator: str
    tax: Tax
    total_tax_base: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    order_references: Sequence[OrderReference] = field(default_factory=tuple)
    references: Sequence[str] = field(default_factory=tuple)
    tax_exemption_code: Optional[str] = None

    def __post_init__(self) -> None:
        self.order_references = tuple(
            _coerce_dataclass(item, OrderReference, "OrderReferences") for item in _ensure_sequence(self.order_references, "OrderReferences")
        )
        self.tax_point_date = _ensure_date(self.tax_point_date, "TaxPointDate")
        self.references = tuple(
            _ensure_str(ref, "Reference", min_len=1, max_len=60) for ref in _ensure_sequence(self.references, "Reference")
        )
        self.debit_credit_indicator = _ensure_str(
            self.debit_credit_indicator,
            "DebitCreditIndicator",
            upper=True,
        )
        if self.debit_credit_indicator not in _DEBIT_CREDIT:
            raise PayloadValidationError("DebitCreditIndicator deve ser D ou C.")
        if (self.total_tax_base is None) == (self.amount is None):
            raise PayloadValidationError("Indique TotalTaxBase ou Amount (um e só um).")
        if self.total_tax_base is not None:
            self.total_tax_base = _ensure_decimal(
                self.total_tax_base,
                "TotalTaxBase",
                min_value=_MONETARY_MIN,
                max_value=_MONETARY_MAX,
            )
        if self.amount is not None:
            self.amount = _ensure_decimal(
                self.amount,
                "Amount",
                min_value=_MONETARY_MIN,
                max_value=_MONETARY_MAX,
            )
        self.tax = _coerce_dataclass(self.tax, Tax, "Tax")
        if self.tax_exemption_code is not None:
            self.tax_exemption_code = _ensure_str(
                self.tax_exemption_code,
                "TaxExemptionCode",
                pattern=_TAX_EXEMPTION_RE,
            )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "InvoiceLineSummary":
        return cls(
            order_references=data.get("OrderReferences") or (),
            tax_point_date=data.get("TaxPointDate"),
            references=data.get("Reference") or data.get("References") or (),
            debit_credit_indicator=data.get("DebitCreditIndicator"),
            total_tax_base=data.get("TotalTaxBase"),
            amount=data.get("Amount"),
            tax=data.get("Tax"),
            tax_exemption_code=data.get("TaxExemptionCode"),
        )

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.order_references:
            payload["OrderReferences"] = [ref.to_payload() for ref in self.order_references]
        payload.update(
            {
                "TaxPointDate": self.tax_point_date,
                "DebitCreditIndicator": self.debit_credit_indicator,
            }
        )
        if self.references:
            payload["Reference"] = list(self.references)
        if self.total_tax_base is not None:
            payload["TotalTaxBase"] = self.total_tax_base
        if self.amount is not None:
            payload["Amount"] = self.amount
        payload["Tax"] = self.tax
        if self.tax_exemption_code is not None:
            payload["TaxExemptionCode"] = self.tax_exemption_code
        return payload


@dataclass
class WorkLineSummary:
    tax_point_date: date
    debit_credit_indicator: str
    total_tax_base: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    tax: Optional[Tax] = None
    order_references: Sequence[OrderReference] = field(default_factory=tuple)
    references: Sequence[str] = field(default_factory=tuple)
    tax_exemption_code: Optional[str] = None

    def __post_init__(self) -> None:
        self.order_references = tuple(
            _coerce_dataclass(item, OrderReference, "OrderReferences") for item in _ensure_sequence(self.order_references, "OrderReferences")
        )
        self.tax_point_date = _ensure_date(self.tax_point_date, "TaxPointDate")
        self.references = tuple(
            _ensure_str(ref, "Reference", min_len=1, max_len=60) for ref in _ensure_sequence(self.references, "Reference")
        )
        self.debit_credit_indicator = _ensure_str(
            self.debit_credit_indicator,
            "DebitCreditIndicator",
            upper=True,
        )
        if self.debit_credit_indicator not in _DEBIT_CREDIT:
            raise PayloadValidationError("DebitCreditIndicator deve ser D ou C.")
        if (self.total_tax_base is None) == (self.amount is None):
            raise PayloadValidationError("Indique TotalTaxBase ou Amount (um e só um).")
        if self.total_tax_base is not None:
            self.total_tax_base = _ensure_decimal(
                self.total_tax_base,
                "TotalTaxBase",
                min_value=_MONETARY_MIN,
                max_value=_MONETARY_MAX,
            )
        if self.amount is not None:
            self.amount = _ensure_decimal(
                self.amount,
                "Amount",
                min_value=_MONETARY_MIN,
                max_value=_MONETARY_MAX,
            )
        if self.tax is not None:
            self.tax = _coerce_dataclass(self.tax, Tax, "Tax")
        if self.tax_exemption_code is not None:
            self.tax_exemption_code = _ensure_str(
                self.tax_exemption_code,
                "TaxExemptionCode",
                pattern=_TAX_EXEMPTION_RE,
            )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "WorkLineSummary":
        return cls(
            order_references=data.get("OrderReferences") or (),
            tax_point_date=data.get("TaxPointDate"),
            references=data.get("Reference") or data.get("References") or (),
            debit_credit_indicator=data.get("DebitCreditIndicator"),
            total_tax_base=data.get("TotalTaxBase"),
            amount=data.get("Amount"),
            tax=data.get("Tax"),
            tax_exemption_code=data.get("TaxExemptionCode"),
        )

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.order_references:
            payload["OrderReferences"] = [ref.to_payload() for ref in self.order_references]
        payload.update(
            {
                "TaxPointDate": self.tax_point_date,
                "DebitCreditIndicator": self.debit_credit_indicator,
            }
        )
        if self.references:
            payload["Reference"] = list(self.references)
        if self.total_tax_base is not None:
            payload["TotalTaxBase"] = self.total_tax_base
        if self.amount is not None:
            payload["Amount"] = self.amount
        if self.tax is not None:
            payload["Tax"] = self.tax
        if self.tax_exemption_code is not None:
            payload["TaxExemptionCode"] = self.tax_exemption_code
        return payload


@dataclass
class PaymentLineSummary:
    source_document_ids: Sequence[SourceDocumentID]
    debit_credit_indicator: str
    amount: Decimal
    settlement_amount: Optional[Decimal] = None
    tax: Optional[Tax] = None
    tax_exemption_code: Optional[str] = None

    def __post_init__(self) -> None:
        self.source_document_ids = tuple(
            _coerce_dataclass(item, SourceDocumentID, "SourceDocumentID")
            for item in _ensure_sequence(self.source_document_ids, "SourceDocumentID")
        )
        if not self.source_document_ids:
            raise PayloadValidationError("SourceDocumentID deve ter pelo menos 1 elemento.")
        self.debit_credit_indicator = _ensure_str(
            self.debit_credit_indicator,
            "DebitCreditIndicator",
            upper=True,
        )
        if self.debit_credit_indicator not in _DEBIT_CREDIT:
            raise PayloadValidationError("DebitCreditIndicator deve ser D ou C.")
        self.amount = _ensure_decimal(
            self.amount,
            "Amount",
            min_value=_MONETARY_MIN,
            max_value=_MONETARY_MAX,
        )
        if self.settlement_amount is not None:
            self.settlement_amount = _ensure_decimal(
                self.settlement_amount,
                "SettlementAmount",
                min_value=_MONETARY_MIN,
                max_value=_MONETARY_MAX,
            )
        if self.tax is not None:
            self.tax = _coerce_dataclass(self.tax, Tax, "Tax")
        if self.tax_exemption_code is not None:
            self.tax_exemption_code = _ensure_str(
                self.tax_exemption_code,
                "TaxExemptionCode",
                pattern=_TAX_EXEMPTION_RE,
            )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "PaymentLineSummary":
        return cls(
            source_document_ids=data.get("SourceDocumentID") or (),
            settlement_amount=data.get("SettlementAmount"),
            debit_credit_indicator=data.get("DebitCreditIndicator"),
            amount=data.get("Amount"),
            tax=data.get("Tax"),
            tax_exemption_code=data.get("TaxExemptionCode"),
        )

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "SourceDocumentID": [src.to_payload() for src in self.source_document_ids],
            "DebitCreditIndicator": self.debit_credit_indicator,
            "Amount": self.amount,
        }
        if self.settlement_amount is not None:
            payload["SettlementAmount"] = self.settlement_amount
        if self.tax is not None:
            payload["Tax"] = self.tax
        if self.tax_exemption_code is not None:
            payload["TaxExemptionCode"] = self.tax_exemption_code
        return payload


@dataclass
class InvoiceHeader:
    invoice_no: str
    atcud: str
    invoice_date: date
    invoice_type: str
    self_billing_indicator: int
    customer_tax_id: str
    customer_tax_id_country: str

    def __post_init__(self) -> None:
        self.invoice_no = _ensure_str(
            self.invoice_no,
            "InvoiceNo",
            min_len=1,
            max_len=60,
            pattern=_INVOICE_NO_RE,
        )
        self.atcud = _ensure_str(self.atcud, "ATCUD", min_len=1, max_len=100)
        self.invoice_date = _ensure_date(self.invoice_date, "InvoiceDate")
        self.invoice_type = _ensure_str(self.invoice_type, "InvoiceType", upper=True)
        if self.invoice_type not in _INVOICE_TYPES:
            raise PayloadValidationError("InvoiceType inválido.")
        self.self_billing_indicator = _ensure_indicator(
            self.self_billing_indicator,
            "SelfBillingIndicator",
            {0, 1},
        )
        self.customer_tax_id = _ensure_str(
            str(self.customer_tax_id),
            "CustomerTaxID",
            min_len=1,
            max_len=30,
        )
        self.customer_tax_id_country = _ensure_str(
            self.customer_tax_id_country,
            "CustomerTaxIDCountry",
            pattern=_COUNTRY_RE,
            upper=True,
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "InvoiceHeader":
        return cls(
            invoice_no=data.get("InvoiceNo"),
            atcud=data.get("ATCUD"),
            invoice_date=data.get("InvoiceDate"),
            invoice_type=data.get("InvoiceType"),
            self_billing_indicator=data.get("SelfBillingIndicator"),
            customer_tax_id=data.get("CustomerTaxID"),
            customer_tax_id_country=data.get("CustomerTaxIDCountry"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "InvoiceNo": self.invoice_no,
            "ATCUD": self.atcud,
            "InvoiceDate": self.invoice_date,
            "InvoiceType": self.invoice_type,
            "SelfBillingIndicator": self.self_billing_indicator,
            "CustomerTaxID": self.customer_tax_id,
            "CustomerTaxIDCountry": self.customer_tax_id_country,
        }


@dataclass
class InvoiceData(InvoiceHeader):
    document_status: InvoiceStatus
    hash_characters: str
    cash_vat_scheme_indicator: int
    paperless_indicator: int
    system_entry_date: datetime
    document_totals: DocumentTotals
    line_summary: Sequence[InvoiceLineSummary]
    eac_code: Optional[str] = None
    withholding_tax: Sequence[WithholdingTax] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        super().__post_init__()
        self.document_status = _coerce_dataclass(self.document_status, InvoiceStatus, "DocumentStatus")
        self.hash_characters = _ensure_str(
            self.hash_characters,
            "HashCharacters",
            pattern=_HASH_CHARS_RE,
        )
        self.cash_vat_scheme_indicator = _ensure_indicator(
            self.cash_vat_scheme_indicator,
            "CashVATSchemeIndicator",
            {0, 1},
        )
        self.paperless_indicator = _ensure_indicator(
            self.paperless_indicator,
            "PaperLessIndicator",
            {0, 1},
        )
        if self.eac_code is not None:
            self.eac_code = _ensure_str(self.eac_code, "EACCode", pattern=_EAC_RE)
        self.system_entry_date = _ensure_datetime(self.system_entry_date, "SystemEntryDate")
        self.line_summary = tuple(
            _coerce_dataclass(item, InvoiceLineSummary, "LineSummary") for item in _ensure_sequence(self.line_summary, "LineSummary")
        )
        if not self.line_summary:
            raise PayloadValidationError("LineSummary deve ter pelo menos 1 linha.")
        self.document_totals = _coerce_dataclass(self.document_totals, DocumentTotals, "DocumentTotals")
        self.withholding_tax = tuple(
            _coerce_dataclass(item, WithholdingTax, "WithholdingTax")
            for item in _ensure_sequence(self.withholding_tax, "WithholdingTax")
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "InvoiceData":
        return cls(
            invoice_no=data.get("InvoiceNo"),
            atcud=data.get("ATCUD"),
            invoice_date=data.get("InvoiceDate"),
            invoice_type=data.get("InvoiceType"),
            self_billing_indicator=data.get("SelfBillingIndicator"),
            customer_tax_id=data.get("CustomerTaxID"),
            customer_tax_id_country=data.get("CustomerTaxIDCountry"),
            document_status=data.get("DocumentStatus"),
            hash_characters=data.get("HashCharacters", ""),
            cash_vat_scheme_indicator=data.get("CashVATSchemeIndicator", 0),
            paperless_indicator=data.get("PaperLessIndicator", 0),
            eac_code=data.get("EACCode"),
            system_entry_date=data.get("SystemEntryDate"),
            line_summary=data.get("LineSummary") or (),
            document_totals=data.get("DocumentTotals"),
            withholding_tax=data.get("WithholdingTax") or (),
        )

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        payload.update(
            {
                "DocumentStatus": self.document_status,
                "HashCharacters": self.hash_characters,
                "CashVATSchemeIndicator": self.cash_vat_scheme_indicator,
                "PaperLessIndicator": self.paperless_indicator,
                "SystemEntryDate": self.system_entry_date,
                "LineSummary": [line for line in self.line_summary],
                "DocumentTotals": self.document_totals,
            }
        )
        if self.eac_code is not None:
            payload["EACCode"] = self.eac_code
        if self.withholding_tax:
            payload["WithholdingTax"] = [wt for wt in self.withholding_tax]
        return payload


@dataclass
class WorkHeader:
    document_number: str
    atcud: str
    work_date: date
    work_type: str
    customer_tax_id: str
    customer_tax_id_country: str

    def __post_init__(self) -> None:
        self.document_number = _ensure_str(
            self.document_number,
            "DocumentNumber",
            min_len=1,
            max_len=60,
            pattern=_INVOICE_NO_RE,
        )
        self.atcud = _ensure_str(self.atcud, "ATCUD", min_len=1, max_len=100)
        self.work_date = _ensure_date(self.work_date, "WorkDate")
        self.work_type = _ensure_str(self.work_type, "WorkType", upper=True)
        if self.work_type not in _WORK_TYPES:
            raise PayloadValidationError("WorkType inválido.")
        self.customer_tax_id = _ensure_str(
            str(self.customer_tax_id),
            "CustomerTaxID",
            min_len=1,
            max_len=30,
        )
        self.customer_tax_id_country = _ensure_str(
            self.customer_tax_id_country,
            "CustomerTaxIDCountry",
            pattern=_COUNTRY_RE,
            upper=True,
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "WorkHeader":
        return cls(
            document_number=data.get("DocumentNumber"),
            atcud=data.get("ATCUD"),
            work_date=data.get("WorkDate"),
            work_type=data.get("WorkType"),
            customer_tax_id=data.get("CustomerTaxID"),
            customer_tax_id_country=data.get("CustomerTaxIDCountry"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "DocumentNumber": self.document_number,
            "ATCUD": self.atcud,
            "WorkDate": self.work_date,
            "WorkType": self.work_type,
            "CustomerTaxID": self.customer_tax_id,
            "CustomerTaxIDCountry": self.customer_tax_id_country,
        }


@dataclass
class WorkData(WorkHeader):
    document_status: WorkStatus
    hash_characters: str
    system_entry_date: datetime
    document_totals: DocumentTotals
    line_summary: Sequence[WorkLineSummary]
    eac_code: Optional[str] = None

    def __post_init__(self) -> None:
        super().__post_init__()
        self.document_status = _coerce_dataclass(self.document_status, WorkStatus, "DocumentStatus")
        self.hash_characters = _ensure_str(
            self.hash_characters,
            "HashCharacters",
            pattern=_HASH_CHARS_RE,
        )
        if self.eac_code is not None:
            self.eac_code = _ensure_str(self.eac_code, "EACCode", pattern=_EAC_RE)
        self.system_entry_date = _ensure_datetime(self.system_entry_date, "SystemEntryDate")
        self.line_summary = tuple(
            _coerce_dataclass(item, WorkLineSummary, "LineSummary") for item in _ensure_sequence(self.line_summary, "LineSummary")
        )
        if not self.line_summary:
            raise PayloadValidationError("LineSummary deve ter pelo menos 1 linha.")
        self.document_totals = _coerce_dataclass(self.document_totals, DocumentTotals, "DocumentTotals")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "WorkData":
        return cls(
            document_number=data.get("DocumentNumber"),
            atcud=data.get("ATCUD"),
            work_date=data.get("WorkDate"),
            work_type=data.get("WorkType"),
            customer_tax_id=data.get("CustomerTaxID"),
            customer_tax_id_country=data.get("CustomerTaxIDCountry"),
            document_status=data.get("DocumentStatus"),
            hash_characters=data.get("HashCharacters", ""),
            eac_code=data.get("EACCode"),
            system_entry_date=data.get("SystemEntryDate"),
            line_summary=data.get("LineSummary") or (),
            document_totals=data.get("DocumentTotals"),
        )

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        payload.update(
            {
                "DocumentStatus": self.document_status,
                "HashCharacters": self.hash_characters,
                "SystemEntryDate": self.system_entry_date,
                "LineSummary": [line for line in self.line_summary],
                "DocumentTotals": self.document_totals,
            }
        )
        if self.eac_code is not None:
            payload["EACCode"] = self.eac_code
        return payload


@dataclass
class PaymentHeader:
    payment_ref_no: str
    atcud: str
    transaction_date: date
    payment_type: str
    customer_tax_id: str
    customer_tax_id_country: str

    def __post_init__(self) -> None:
        self.payment_ref_no = _ensure_str(
            self.payment_ref_no,
            "PaymentRefNo",
            min_len=1,
            max_len=60,
            pattern=_INVOICE_NO_RE,
        )
        self.atcud = _ensure_str(self.atcud, "ATCUD", min_len=1, max_len=100)
        self.transaction_date = _ensure_date(self.transaction_date, "TransactionDate")
        self.payment_type = _ensure_str(self.payment_type, "PaymentType", upper=True)
        if self.payment_type not in _PAYMENT_TYPES:
            raise PayloadValidationError("PaymentType inválido.")
        self.customer_tax_id = _ensure_str(
            str(self.customer_tax_id),
            "CustomerTaxID",
            min_len=1,
            max_len=30,
        )
        self.customer_tax_id_country = _ensure_str(
            self.customer_tax_id_country,
            "CustomerTaxIDCountry",
            pattern=_COUNTRY_RE,
            upper=True,
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "PaymentHeader":
        return cls(
            payment_ref_no=data.get("PaymentRefNo"),
            atcud=data.get("ATCUD"),
            transaction_date=data.get("TransactionDate"),
            payment_type=data.get("PaymentType"),
            customer_tax_id=data.get("CustomerTaxID"),
            customer_tax_id_country=data.get("CustomerTaxIDCountry"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "PaymentRefNo": self.payment_ref_no,
            "ATCUD": self.atcud,
            "TransactionDate": self.transaction_date,
            "PaymentType": self.payment_type,
            "CustomerTaxID": self.customer_tax_id,
            "CustomerTaxIDCountry": self.customer_tax_id_country,
        }


@dataclass
class PaymentData(PaymentHeader):
    document_status: PaymentStatus
    system_entry_date: datetime
    document_totals: DocumentTotals
    line_summary: Sequence[PaymentLineSummary]
    withholding_tax: Sequence[WithholdingTax] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        super().__post_init__()
        self.document_status = _coerce_dataclass(self.document_status, PaymentStatus, "DocumentStatus")
        self.system_entry_date = _ensure_datetime(self.system_entry_date, "SystemEntryDate")
        self.line_summary = tuple(
            _coerce_dataclass(item, PaymentLineSummary, "LineSummary") for item in _ensure_sequence(self.line_summary, "LineSummary")
        )
        if not self.line_summary:
            raise PayloadValidationError("LineSummary deve ter pelo menos 1 linha.")
        self.document_totals = _coerce_dataclass(self.document_totals, DocumentTotals, "DocumentTotals")
        self.withholding_tax = tuple(
            _coerce_dataclass(item, WithholdingTax, "WithholdingTax")
            for item in _ensure_sequence(self.withholding_tax, "WithholdingTax")
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "PaymentData":
        return cls(
            payment_ref_no=data.get("PaymentRefNo"),
            atcud=data.get("ATCUD"),
            transaction_date=data.get("TransactionDate"),
            payment_type=data.get("PaymentType"),
            customer_tax_id=data.get("CustomerTaxID"),
            customer_tax_id_country=data.get("CustomerTaxIDCountry"),
            document_status=data.get("DocumentStatus"),
            system_entry_date=data.get("SystemEntryDate"),
            line_summary=data.get("LineSummary") or (),
            document_totals=data.get("DocumentTotals"),
            withholding_tax=data.get("WithholdingTax") or (),
        )

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        payload.update(
            {
                "DocumentStatus": self.document_status,
                "SystemEntryDate": self.system_entry_date,
                "LineSummary": [line for line in self.line_summary],
                "DocumentTotals": self.document_totals,
            }
        )
        if self.withholding_tax:
            payload["WithholdingTax"] = [wt for wt in self.withholding_tax]
        return payload


_EFATURA_MD_RE = re.compile(r"\d+\.\d+\.\d+")


def _validate_md_version(value: Any) -> str:
    text = _ensure_str(value, "eFaturaMDVersion", min_len=1, max_len=10)
    if not _EFATURA_MD_RE.fullmatch(text):
        msg = "eFaturaMDVersion deve ter o formato 'x.x.x' (ex.: 0.0.1)."
        raise PayloadValidationError(msg)
    return text


def _validate_audit_file_version(value: Any) -> str:
    text = _ensure_str(value, "AuditFileVersion", min_len=1, max_len=20)
    if text not in _AUDIT_FILE_VERSIONS:
        allowed = ", ".join(sorted(_AUDIT_FILE_VERSIONS))
        msg = f"AuditFileVersion inválido. Valores permitidos: {allowed}."
        raise PayloadValidationError(msg)
    return text


def _validate_tax_registration_number(value: Any) -> int:
    number = _ensure_int(value, "TaxRegistrationNumber", min_value=_VAT_MIN, max_digits=9)
    if number < _VAT_MIN or number > _VAT_MAX:
        msg = "TaxRegistrationNumber deve ter 9 dígitos (NIF PT)."
        raise PayloadValidationError(msg)
    return number


def _validate_tax_entity(value: Any) -> str:
    return _ensure_str(value, "TaxEntity", min_len=1, max_len=20)


def _validate_reason(value: Any) -> str:
    return _ensure_str(value, "reason", min_len=10, max_len=500)


def _validate_software_cert(value: Any) -> int:
    return _ensure_int(value, "SoftwareCertificateNumber", min_value=0, max_digits=10)


def _coerce_channel(value: Any) -> Optional[ChannelInfo]:
    if value is None:
        return None
    return _coerce_dataclass(value, ChannelInfo, "CanalRegisto")


def _coerce_date_range(value: Any) -> Optional[DateRange]:
    if value is None:
        return None
    return _coerce_dataclass(value, DateRange, "date_range")


@dataclass
class RegisterInvoiceInput:
    efatura_md_version: str
    audit_file_version: str
    tax_registration_number: str | int
    tax_entity: str
    software_certificate_number: int
    invoice_data: InvoiceData | Mapping[str, Any]
    canal_registo: Optional[ChannelInfo] = None

    def __post_init__(self) -> None:
        self.efatura_md_version = _validate_md_version(self.efatura_md_version)
        self.audit_file_version = _validate_audit_file_version(self.audit_file_version)
        self.tax_registration_number = _validate_tax_registration_number(self.tax_registration_number)
        self.tax_entity = _validate_tax_entity(self.tax_entity)
        self.software_certificate_number = _validate_software_cert(self.software_certificate_number)
        self.invoice_data = _coerce_dataclass(self.invoice_data, InvoiceData, "InvoiceData")
        self.canal_registo = _coerce_channel(self.canal_registo)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "eFaturaMDVersion": self.efatura_md_version,
            "AuditFileVersion": self.audit_file_version,
            "TaxRegistrationNumber": self.tax_registration_number,
            "TaxEntity": self.tax_entity,
            "SoftwareCertificateNumber": self.software_certificate_number,
            "InvoiceData": self.invoice_data,
        }
        if self.canal_registo:
            payload["CanalRegisto"] = self.canal_registo.to_payload()
        return payload


@dataclass
class ChangeInvoiceStatusInput:
    efatura_md_version: str
    tax_registration_number: str | int
    invoice_header: InvoiceHeader | Mapping[str, Any]
    invoice_status: NewInvoiceStatus | Mapping[str, Any]
    canal_registo: Optional[ChannelInfo] = None

    def __post_init__(self) -> None:
        self.efatura_md_version = _validate_md_version(self.efatura_md_version)
        self.tax_registration_number = _validate_tax_registration_number(self.tax_registration_number)
        self.invoice_header = _coerce_dataclass(self.invoice_header, InvoiceHeader, "InvoiceHeader")
        self.invoice_status = _coerce_dataclass(self.invoice_status, NewInvoiceStatus, "InvoiceStatus")
        self.canal_registo = _coerce_channel(self.canal_registo)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "eFaturaMDVersion": self.efatura_md_version,
            "TaxRegistrationNumber": self.tax_registration_number,
            "InvoiceHeader": self.invoice_header,
            "InvoiceStatus": self.invoice_status,
        }
        if self.canal_registo:
            payload["CanalRegisto"] = self.canal_registo.to_payload()
        return payload


@dataclass
class DeleteInvoiceInput:
    efatura_md_version: str
    tax_registration_number: str | int
    reason: str
    documents_list: Optional[Sequence[InvoiceHeader | Mapping[str, Any]]] = None
    date_range: Optional[DateRange] = None
    canal_registo: Optional[ChannelInfo] = None

    def __post_init__(self) -> None:
        self.efatura_md_version = _validate_md_version(self.efatura_md_version)
        self.tax_registration_number = _validate_tax_registration_number(self.tax_registration_number)
        self.reason = _validate_reason(self.reason)
        self.date_range = _coerce_date_range(self.date_range)
        if self.documents_list is not None:
            self.documents_list = _coerce_list(
                self.documents_list,
                InvoiceHeader,
                "documents_list",
            )
        if not self.documents_list and not self.date_range:
            msg = "É necessário indicar documents_list ou date_range."
            raise PayloadValidationError(msg)
        if self.documents_list and self.date_range:
            msg = "Indique apenas documents_list ou date_range, não ambos."
            raise PayloadValidationError(msg)
        self.canal_registo = _coerce_channel(self.canal_registo)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "eFaturaMDVersion": self.efatura_md_version,
            "TaxRegistrationNumber": self.tax_registration_number,
            "reason": self.reason,
        }
        if self.documents_list:
            payload["documentsList"] = {
                "invoice": list(self.documents_list),
            }
        elif self.date_range:
            payload["dateRange"] = self.date_range.to_payload()
        if self.canal_registo:
            payload["CanalRegisto"] = self.canal_registo.to_payload()
        return payload


@dataclass
class RegisterWorkInput:
    efatura_md_version: str
    audit_file_version: str
    tax_registration_number: str | int
    tax_entity: str
    software_certificate_number: int
    work_data: WorkData | Mapping[str, Any]
    canal_registo: Optional[ChannelInfo] = None

    def __post_init__(self) -> None:
        self.efatura_md_version = _validate_md_version(self.efatura_md_version)
        self.audit_file_version = _validate_audit_file_version(self.audit_file_version)
        self.tax_registration_number = _validate_tax_registration_number(self.tax_registration_number)
        self.tax_entity = _validate_tax_entity(self.tax_entity)
        self.software_certificate_number = _validate_software_cert(self.software_certificate_number)
        self.work_data = _coerce_dataclass(self.work_data, WorkData, "WorkData")
        self.canal_registo = _coerce_channel(self.canal_registo)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "eFaturaMDVersion": self.efatura_md_version,
            "AuditFileVersion": self.audit_file_version,
            "TaxRegistrationNumber": self.tax_registration_number,
            "TaxEntity": self.tax_entity,
            "SoftwareCertificateNumber": self.software_certificate_number,
            "WorkData": self.work_data,
        }
        if self.canal_registo:
            payload["CanalRegisto"] = self.canal_registo.to_payload()
        return payload


@dataclass
class ChangeWorkStatusInput:
    efatura_md_version: str
    tax_registration_number: str | int
    work_header: WorkHeader | Mapping[str, Any]
    work_status: NewWorkStatus | Mapping[str, Any]
    canal_registo: Optional[ChannelInfo] = None

    def __post_init__(self) -> None:
        self.efatura_md_version = _validate_md_version(self.efatura_md_version)
        self.tax_registration_number = _validate_tax_registration_number(self.tax_registration_number)
        self.work_header = _coerce_dataclass(self.work_header, WorkHeader, "WorkHeader")
        self.work_status = _coerce_dataclass(self.work_status, NewWorkStatus, "WorkStatus")
        self.canal_registo = _coerce_channel(self.canal_registo)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "eFaturaMDVersion": self.efatura_md_version,
            "TaxRegistrationNumber": self.tax_registration_number,
            "WorkHeader": self.work_header,
            "WorkStatus": self.work_status,
        }
        if self.canal_registo:
            payload["CanalRegisto"] = self.canal_registo.to_payload()
        return payload


@dataclass
class DeleteWorkInput:
    efatura_md_version: str
    tax_registration_number: str | int
    reason: str
    documents_list: Optional[Sequence[WorkHeader | Mapping[str, Any]]] = None
    date_range: Optional[DateRange] = None
    canal_registo: Optional[ChannelInfo] = None

    def __post_init__(self) -> None:
        self.efatura_md_version = _validate_md_version(self.efatura_md_version)
        self.tax_registration_number = _validate_tax_registration_number(self.tax_registration_number)
        self.reason = _validate_reason(self.reason)
        self.date_range = _coerce_date_range(self.date_range)
        if self.documents_list is not None:
            self.documents_list = _coerce_list(self.documents_list, WorkHeader, "documents_list")
        if not self.documents_list and not self.date_range:
            msg = "É necessário indicar documents_list ou date_range."
            raise PayloadValidationError(msg)
        if self.documents_list and self.date_range:
            msg = "Indique apenas documents_list ou date_range, não ambos."
            raise PayloadValidationError(msg)
        self.canal_registo = _coerce_channel(self.canal_registo)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "eFaturaMDVersion": self.efatura_md_version,
            "TaxRegistrationNumber": self.tax_registration_number,
            "reason": self.reason,
        }
        if self.documents_list:
            payload["documentsList"] = {
                "work": list(self.documents_list),
            }
        elif self.date_range:
            payload["dateRange"] = self.date_range.to_payload()
        if self.canal_registo:
            payload["CanalRegisto"] = self.canal_registo.to_payload()
        return payload


@dataclass
class RegisterPaymentInput:
    efatura_md_version: str
    audit_file_version: str
    tax_registration_number: str | int
    tax_entity: str
    software_certificate_number: int
    payment_data: PaymentData | Mapping[str, Any]
    canal_registo: Optional[ChannelInfo] = None

    def __post_init__(self) -> None:
        self.efatura_md_version = _validate_md_version(self.efatura_md_version)
        self.audit_file_version = _validate_audit_file_version(self.audit_file_version)
        self.tax_registration_number = _validate_tax_registration_number(self.tax_registration_number)
        self.tax_entity = _validate_tax_entity(self.tax_entity)
        self.software_certificate_number = _validate_software_cert(self.software_certificate_number)
        self.payment_data = _coerce_dataclass(self.payment_data, PaymentData, "PaymentData")
        self.canal_registo = _coerce_channel(self.canal_registo)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "eFaturaMDVersion": self.efatura_md_version,
            "AuditFileVersion": self.audit_file_version,
            "TaxRegistrationNumber": self.tax_registration_number,
            "TaxEntity": self.tax_entity,
            "SoftwareCertificateNumber": self.software_certificate_number,
            "PaymentData": self.payment_data,
        }
        if self.canal_registo:
            payload["CanalRegisto"] = self.canal_registo.to_payload()
        return payload


@dataclass
class ChangePaymentStatusInput:
    efatura_md_version: str
    tax_registration_number: str | int
    payment_header: PaymentHeader | Mapping[str, Any]
    payment_status: NewPaymentStatus | Mapping[str, Any]
    canal_registo: Optional[ChannelInfo] = None

    def __post_init__(self) -> None:
        self.efatura_md_version = _validate_md_version(self.efatura_md_version)
        self.tax_registration_number = _validate_tax_registration_number(self.tax_registration_number)
        self.payment_header = _coerce_dataclass(self.payment_header, PaymentHeader, "PaymentHeader")
        self.payment_status = _coerce_dataclass(self.payment_status, NewPaymentStatus, "PaymentStatus")
        self.canal_registo = _coerce_channel(self.canal_registo)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "eFaturaMDVersion": self.efatura_md_version,
            "TaxRegistrationNumber": self.tax_registration_number,
            "PaymentHeader": self.payment_header,
            "PaymentStatus": self.payment_status,
        }
        if self.canal_registo:
            payload["CanalRegisto"] = self.canal_registo.to_payload()
        return payload


@dataclass
class DeletePaymentInput:
    efatura_md_version: str
    tax_registration_number: str | int
    reason: str
    documents_list: Optional[Sequence[PaymentHeader | Mapping[str, Any]]] = None
    date_range: Optional[DateRange] = None
    canal_registo: Optional[ChannelInfo] = None

    def __post_init__(self) -> None:
        self.efatura_md_version = _validate_md_version(self.efatura_md_version)
        self.tax_registration_number = _validate_tax_registration_number(self.tax_registration_number)
        self.reason = _validate_reason(self.reason)
        self.date_range = _coerce_date_range(self.date_range)
        if self.documents_list is not None:
            self.documents_list = _coerce_list(
                self.documents_list,
                PaymentHeader,
                "documents_list",
            )
        if not self.documents_list and not self.date_range:
            msg = "É necessário indicar documents_list ou date_range."
            raise PayloadValidationError(msg)
        if self.documents_list and self.date_range:
            msg = "Indique apenas documents_list ou date_range, não ambos."
            raise PayloadValidationError(msg)
        self.canal_registo = _coerce_channel(self.canal_registo)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "eFaturaMDVersion": self.efatura_md_version,
            "TaxRegistrationNumber": self.tax_registration_number,
            "reason": self.reason,
        }
        if self.documents_list:
            payload["documentsList"] = {
                "payment": list(self.documents_list),
            }
        elif self.date_range:
            payload["dateRange"] = self.date_range.to_payload()
        if self.canal_registo:
            payload["CanalRegisto"] = self.canal_registo.to_payload()
        return payload


@dataclass
class OperationResponse:
    codigo_resposta: Optional[int]
    mensagem: Optional[str]
    data_operacao: Optional[datetime]

    @property
    def ok(self) -> bool:
        return self.codigo_resposta == 0


class FaturasError(Exception):
    """Erros específicos para operações Fatcorews."""


class FaturasService:
    """Cliente para o serviço Fatcorews baseado no WSDL oficial."""

    _SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
    _WS_NS = "http://factemi.at.min_financas.pt/documents"
    _NS = {"soap": _SOAP_NS, "fat": _WS_NS}

    def __init__(
        self,
        client: _WSClient,
        *,
        endpoint: Optional[str] = None,
        validate_xml: bool = False,
    ) -> None:
        self._client = client
        self._endpoint_override = endpoint
        self._last_request_xml: Optional[str] = None
        self._last_response_text: Optional[str] = None
        self._last_response_status: Optional[int] = None
        self._schema = self._maybe_load_validator(validate_xml)

    # ---------- helpers ----------

    def _build_body(self, root_tag: str, payload: Mapping[str, Any]) -> str:
        root = ET.Element(f"{{{self._WS_NS}}}{root_tag}")
        for key, value in payload.items():
            self._append_value(root, key, value)
        xml_payload = ET.tostring(root, encoding="unicode")
        return f"<S:Body>{xml_payload}</S:Body>"

    def _append_value(self, parent: ET.Element, tag: str, value: Any) -> None:
        prepared = self._prepare_value(value)
        if prepared is None:
            return
        if isinstance(prepared, (list, tuple)):
            for item in prepared:
                self._append_value(parent, tag, item)
            return
        element = ET.SubElement(parent, f"{{{self._WS_NS}}}{tag}")
        if isinstance(prepared, Mapping):
            for child_tag, child_value in prepared.items():
                self._append_value(element, child_tag, child_value)
        else:
            element.text = self._serialize_value(prepared)

    @staticmethod
    def _prepare_value(value: Any) -> Any:
        if value is None:
            return None
        if hasattr(value, "to_payload"):
            return value.to_payload()  # type: ignore[no-any-return]
        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, Mapping):
            return value
        if isinstance(value, (list, tuple)):
            return value
        return value

    def _attach_last_exchange_to_exception(self, exc: FaturasError) -> FaturasError:
        if not getattr(exc, "last_request_xml", None):
            exc.last_request_xml = (
                self._last_request_xml or getattr(self._client, "_last_request_xml", None)
            )
        if not getattr(exc, "last_response_text", None):
            exc.last_response_text = self._last_response_text
        if not getattr(exc, "last_response_status", None):
            exc.last_response_status = self._last_response_status
        return exc

    @staticmethod
    def _serialize_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, datetime):
            return value.replace(microsecond=0).isoformat()
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, Decimal):
            return format(value, "f")
        return str(value)

    def _maybe_load_validator(self, enabled: bool):
        if not enabled:
            return None
        try:
            import xmlschema  # type: ignore
        except ImportError as exc:  # noqa: WPS440
            msg = "Para validate_xml=True, instale o extra 'xmlschema' (pip install xmlschema)."
            raise FaturasError(msg) from exc
        wsdl_path = Path(__file__).with_name("wsdl") / "Fatcorews.wsdl"
        try:
            tree = ET.parse(wsdl_path)
        except OSError as exc:
            raise FaturasError(f"WSDL Fatcorews não encontrado em {wsdl_path}") from exc
        schema_element = tree.find(".//{http://www.w3.org/2001/XMLSchema}schema")
        if schema_element is None:
            raise FaturasError("WSDL Fatcorews não contém schema XSD para validação.")
        return xmlschema.XMLSchema(ET.ElementTree(schema_element))

    def _validate_request_xml(self, envelope_xml: str, request_tag: str) -> None:
        if not self._schema:
            return
        try:
            root = ET.fromstring(envelope_xml)
        except ET.ParseError as exc:
            raise FaturasError(f"Envelope SOAP inválido: {exc}") from exc
        element = root.find(f".//fat:{request_tag}", self._NS)
        if element is None:
            raise FaturasError(f"Elemento {request_tag} não encontrado na validação XSD.")
        try:
            self._schema.validate(element)
        except Exception as exc:  # noqa: BLE001
            raise FaturasError(f"Payload não cumpre o XSD: {exc}") from exc

    def _call_operation(
        self,
        request_tag: str,
        payload: Mapping[str, Any],
        response_tag: str,
    ) -> OperationResponse:
        body_xml = self._build_body(request_tag, payload)
        envelope_xml = self._client.build_envelope_xml(body_xml)
        self._last_request_xml = envelope_xml
        self._last_response_text = None
        self._last_response_status = None
        try:
            self._validate_request_xml(envelope_xml, request_tag)
        except FaturasError as exc:
            raise self._attach_last_exchange_to_exception(exc)
        response = self._client.post(
            service="faturas",
            body_xml=body_xml,
            endpoint=self._endpoint_override,
        )
        response_text = response.text
        self._last_response_text = response_text
        self._last_response_status = response.status_code
        if response.status_code != 200:
            exc = FaturasError(
                f"HTTP {response.status_code} ao chamar {request_tag}: {response_text[:500]}"
            )
            raise self._attach_last_exchange_to_exception(exc)
        try:
            response_element = self._extract_response_element(
                response_text,
                response_tag,
            )
        except FaturasError as exc:
            raise self._attach_last_exchange_to_exception(exc)
        return self._parse_operation_response(response_element)

    def _extract_response_element(self, xml: str, tag: str) -> ET.Element:
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as exc:
            raise FaturasError(f"Resposta XML inválida: {exc}") from exc

        fault = root.find(".//soap:Fault", self._NS)
        if fault is not None:
            code = fault.findtext("faultcode") or ""
            message = fault.findtext("faultstring") or ""
            raise FaturasError(f"SOAP Fault em {tag}: {code} - {message}")

        element = root.find(f".//fat:{tag}", self._NS)
        if element is None:
            raise FaturasError(f"Elemento {tag} não encontrado na resposta SOAP.")
        return element

    @staticmethod
    def _parse_int(text: Optional[str]) -> Optional[int]:
        if text is None:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    @staticmethod
    def _parse_datetime(text: Optional[str]) -> Optional[datetime]:
        if not text:
            return None
        normalized = text.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(normalized, fmt)
                except ValueError:
                    continue
        return None

    def _parse_operation_response(self, element: ET.Element) -> OperationResponse:
        node = element.find("fat:Response", self._NS)
        if node is None:
            raise FaturasError("Elemento Response não encontrado na resposta SOAP.")
        codigo = self._parse_int(
            node.findtext("fat:CodigoResposta", default=None, namespaces=self._NS)
        )
        mensagem = node.findtext("fat:Mensagem", default=None, namespaces=self._NS)
        data_operacao = self._parse_datetime(
            node.findtext("fat:DataOperacao", default=None, namespaces=self._NS)
        )
        return OperationResponse(
            codigo_resposta=codigo,
            mensagem=mensagem,
            data_operacao=data_operacao,
        )

    # ---------- API pública ----------

    def register_invoice(self, data: RegisterInvoiceInput) -> OperationResponse:
        return self._call_operation(
            "RegisterInvoiceRequest",
            data.to_payload(),
            "RegisterInvoiceResponse",
        )

    def change_invoice_status(self, data: ChangeInvoiceStatusInput) -> OperationResponse:
        return self._call_operation(
            "ChangeInvoiceStatusRequest",
            data.to_payload(),
            "ChangeInvoiceStatusResponse",
        )

    def delete_invoice(self, data: DeleteInvoiceInput) -> OperationResponse:
        return self._call_operation(
            "DeleteInvoiceRequest",
            data.to_payload(),
            "DeleteInvoiceResponse",
        )

    def register_work(self, data: RegisterWorkInput) -> OperationResponse:
        return self._call_operation(
            "RegisterWorkRequest",
            data.to_payload(),
            "RegisterWorkResponse",
        )

    def change_work_status(self, data: ChangeWorkStatusInput) -> OperationResponse:
        return self._call_operation(
            "ChangeWorkStatusRequest",
            data.to_payload(),
            "ChangeWorkStatusResponse",
        )

    def delete_work(self, data: DeleteWorkInput) -> OperationResponse:
        return self._call_operation(
            "DeleteWorkRequest",
            data.to_payload(),
            "DeleteWorkResponse",
        )

    def register_payment(self, data: RegisterPaymentInput) -> OperationResponse:
        return self._call_operation(
            "RegisterPaymentRequest",
            data.to_payload(),
            "RegisterPaymentResponse",
        )

    def change_payment_status(
        self,
        data: ChangePaymentStatusInput,
    ) -> OperationResponse:
        return self._call_operation(
            "ChangePaymentStatusRequest",
            data.to_payload(),
            "ChangePaymentStatusResponse",
        )

    def delete_payment(self, data: DeletePaymentInput) -> OperationResponse:
        return self._call_operation(
            "DeletePaymentRequest",
            data.to_payload(),
            "DeletePaymentResponse",
        )
