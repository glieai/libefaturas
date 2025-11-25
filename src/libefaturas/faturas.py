"""Interface de alto nível para o Fatcorews (faturas/obras/pagamentos)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence
import xml.etree.ElementTree as ET
import re

from .client import EFaturasClient
from .fatcore_payloads import (
    ChannelInfo,
    DateRange,
    DocumentTotals,
    InvoiceData,
    InvoiceHeader,
    InvoiceLineSummary,
    InvoiceStatus,
    NewInvoiceStatus,
    OrderReference,
    PaymentData,
    PaymentHeader,
    PaymentLineSummary,
    PaymentStatus,
    NewPaymentStatus,
    PayloadValidationError,
    SourceDocumentID,
    Tax,
    WithholdingTax,
    WorkData,
    WorkHeader,
    WorkLineSummary,
    WorkStatus,
    NewWorkStatus,
    _AUDIT_FILE_VERSIONS,
    _VAT_MAX,
    _VAT_MIN,
    _coerce_dataclass,
    _coerce_list,
    _ensure_int,
    _ensure_str,
)


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
        client: EFaturasClient,
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
