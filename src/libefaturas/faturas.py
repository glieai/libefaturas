"""Interface de alto nível para o Fatcorews (faturas/obras/pagamentos)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping, Optional, Sequence
import xml.etree.ElementTree as ET

from .client import EFaturasClient


__all__ = [
    "ChannelInfo",
    "DateRange",
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


@dataclass
class ChannelInfo:
    sistema: str
    versao: Optional[str] = None

    def to_payload(self) -> dict[str, Any]:
        data: dict[str, Any] = {"Sistema": self.sistema}
        if self.versao:
            data["Versao"] = self.versao
        return data


@dataclass
class DateRange:
    start_date: date
    end_date: date

    def to_payload(self) -> dict[str, Any]:
        return {"StartDate": self.start_date, "EndDate": self.end_date}


@dataclass
class RegisterInvoiceInput:
    efatura_md_version: str
    audit_file_version: str
    tax_registration_number: str | int
    tax_entity: str
    software_certificate_number: int
    invoice_data: NamespacePayload
    canal_registo: Optional[ChannelInfo] = None

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
    invoice_header: NamespacePayload
    invoice_status: NamespacePayload
    canal_registo: Optional[ChannelInfo] = None

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
    documents_list: Optional[Sequence[NamespacePayload]] = None
    date_range: Optional[DateRange] = None
    canal_registo: Optional[ChannelInfo] = None

    def __post_init__(self) -> None:
        if not self.documents_list and not self.date_range:
            msg = "É necessário indicar documents_list ou date_range."
            raise ValueError(msg)
        if self.documents_list and self.date_range:
            msg = "Indique apenas documents_list ou date_range, não ambos."
            raise ValueError(msg)

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
    work_data: NamespacePayload
    canal_registo: Optional[ChannelInfo] = None

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
    work_header: NamespacePayload
    work_status: NamespacePayload
    canal_registo: Optional[ChannelInfo] = None

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
    documents_list: Optional[Sequence[NamespacePayload]] = None
    date_range: Optional[DateRange] = None
    canal_registo: Optional[ChannelInfo] = None

    def __post_init__(self) -> None:
        if not self.documents_list and not self.date_range:
            msg = "É necessário indicar documents_list ou date_range."
            raise ValueError(msg)
        if self.documents_list and self.date_range:
            msg = "Indique apenas documents_list ou date_range, não ambos."
            raise ValueError(msg)

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
    payment_data: NamespacePayload
    canal_registo: Optional[ChannelInfo] = None

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
    payment_header: NamespacePayload
    payment_status: NamespacePayload
    canal_registo: Optional[ChannelInfo] = None

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
    documents_list: Optional[Sequence[NamespacePayload]] = None
    date_range: Optional[DateRange] = None
    canal_registo: Optional[ChannelInfo] = None

    def __post_init__(self) -> None:
        if not self.documents_list and not self.date_range:
            msg = "É necessário indicar documents_list ou date_range."
            raise ValueError(msg)
        if self.documents_list and self.date_range:
            msg = "Indique apenas documents_list ou date_range, não ambos."
            raise ValueError(msg)

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
    ) -> None:
        self._client = client
        self._endpoint_override = endpoint

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

    def _call_operation(
        self,
        request_tag: str,
        payload: Mapping[str, Any],
        response_tag: str,
    ) -> OperationResponse:
        body_xml = self._build_body(request_tag, payload)
        response = self._client.post(
            service="faturas",
            body_xml=body_xml,
            endpoint=self._endpoint_override,
        )
        if response.status_code != 200:
            snippet = response.text[:500]
            raise FaturasError(
                f"HTTP {response.status_code} ao chamar {request_tag}: {snippet}"
            )
        response_element = self._extract_response_element(
            response.text,
            response_tag,
        )
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
