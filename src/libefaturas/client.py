"""Client helpers for interacting with the AT e-fatura webservices."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, TYPE_CHECKING
import xml.etree.ElementTree as ET

import requests

from .config import ENDPOINTS, Environment
from .exceptions import (
    EFaturasAuthError,
    EFaturasConnectionError,
    EFaturasSOAPError,
)
from .retry import RetryConfig, retry_request
from .security import (
    EFaturasCredentials,
    build_security_header_xml,
    build_username_token,
)

if TYPE_CHECKING:
    from .faturas import OperationResponse
    from .series import SeriesListResult, SeriesOperationResult

_logger = logging.getLogger(__name__)

__all__ = ["_WSClient", "EFaturasClient", "EFaturasResult", "test_connection"]


@dataclass
class EFaturasResult:
    ok: bool
    code: int | None
    message: str | None
    data: Any | None

    @classmethod
    def from_operation_response(cls, response: "OperationResponse") -> "EFaturasResult":
        return cls(
            ok=response.ok,
            code=response.codigo_resposta,
            message=response.mensagem,
            data=None,
        )

    @classmethod
    def from_series_list_result(cls, result: "SeriesListResult") -> "EFaturasResult":
        return cls(
            ok=result.result.ok,
            code=result.result.code,
            message=result.result.message,
            data=result.series,
        )

    @classmethod
    def from_series_operation_result(cls, result: "SeriesOperationResult") -> "EFaturasResult":
        return cls(
            ok=result.result.ok,
            code=result.result.code,
            message=result.result.message,
            data=result.series,
        )

    @classmethod
    def from_exception(cls, exc: Exception) -> "EFaturasResult":
        return cls(ok=False, code=None, message=str(exc), data=None)


class _WSClient:
    def __init__(
        self,
        *,
        username: str,
        password: str,
        public_key_path: str | Path,
        client_cert_path: str | Path,
        client_key_path: Optional[str | Path] = None,
        ca_cert_path: Optional[str | Path] = None,
        environment: Environment | str = "test",
        timeout: int | float = 30,
        retry_config: Optional[RetryConfig] = None,
    ) -> None:
        self.username = username
        self.password = password
        self.public_key_path = str(public_key_path)
        self.client_cert_path = str(client_cert_path)
        self.client_key_path = str(client_key_path) if client_key_path is not None else None
        self.ca_cert_path = str(ca_cert_path) if ca_cert_path is not None else None
        self.timeout = timeout
        self.retry_config = retry_config  # None = use default retry config
        if isinstance(environment, Environment):
            self.environment = environment
        else:
            self.environment = Environment(str(environment).lower())
        self._last_request_xml: str | None = None

        creds = EFaturasCredentials(username=username, password=password)
        public_pem = Path(self.public_key_path).read_bytes()
        token = build_username_token(creds, public_pem)
        self._security_header_xml = build_security_header_xml(token)

    def _resolve_endpoint(self, service: str, endpoint: Optional[str]) -> str:
        service_norm = (service or "faturas").lower()
        if endpoint:
            return endpoint
        endpoints = ENDPOINTS[self.environment]
        if service_norm == "series":
            return endpoints.series
        return endpoints.faturas

    def post(
        self,
        *,
        service: str,
        body_xml: str,
        endpoint: Optional[str] = None,
        use_retry: bool = True,
    ) -> requests.Response:
        envelope = self.build_envelope_xml(body_xml)
        self._last_request_xml = envelope

        if self.client_key_path:
            cert = (self.client_cert_path, self.client_key_path)
        else:
            cert = self.client_cert_path

        verify = self.ca_cert_path if self.ca_cert_path else True
        effective_endpoint = self._resolve_endpoint(service, endpoint)

        def _do_request() -> requests.Response:
            return requests.post(
                effective_endpoint,
                data=envelope.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8"},
                cert=cert,
                verify=verify,
                timeout=self.timeout,
            )

        if use_retry:
            return retry_request(
                _do_request,
                config=self.retry_config,
                endpoint=effective_endpoint,
            )
        else:
            try:
                return _do_request()
            except requests.RequestException as exc:
                raise EFaturasConnectionError(
                    f"Erro de ligação: {exc}",
                    endpoint=effective_endpoint,
                    original_error=exc,
                ) from exc

    def build_envelope_xml(self, body_xml: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">'
            f"{self._security_header_xml}"
            f"{body_xml}"
            "</S:Envelope>"
        )


def test_connection(
    *,
    username: str,
    password: str,
    public_key_path: str | Path,
    client_cert_path: str | Path,
    endpoint: Optional[str] = None,
    environment: Environment | str = "test",
    client_key_path: Optional[str | Path] = None,
    ca_cert_path: Optional[str | Path] = None,
    timeout: int | float = 30,
    service: str = "faturas",
) -> Dict[str, Any]:
    """Simplified connectivity test against the AT SOAP endpoints."""
    result: Dict[str, Any] = {
        "username_token_ok": False,
        "tls_ok": False,
        "http_status": None,
        "soap_fault_code": None,
        "soap_fault_string": None,
        "raw_response_snippet": None,
        "error": None,
    }

    try:
        client = _WSClient(
            username=username,
            password=password,
            public_key_path=public_key_path,
            client_cert_path=client_cert_path,
            client_key_path=client_key_path,
            ca_cert_path=ca_cert_path,
            environment=environment,
            timeout=timeout,
        )
        result["username_token_ok"] = True
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"Erro ao gerar UsernameToken: {exc!r}"
        return result

    service_norm = (service or "faturas").lower()

    if service_norm == "series":
        body_xml = (
            "<S:Body>"
            '<consultarSeries xmlns="http://at.gov.pt/"/>'
            "</S:Body>"
        )
    else:
        body_xml = (
            "<S:Body>"
            '<ef:ConnectionTest xmlns:ef="urn:efatura-auth-test">ok</ef:ConnectionTest>'
            "</S:Body>"
        )

    try:
        response = client.post(
            service=service_norm,
            body_xml=body_xml,
            endpoint=endpoint,
        )
        result["tls_ok"] = True
        result["http_status"] = response.status_code
        text = response.text
        result["raw_response_snippet"] = text[:1000]
    except requests.RequestException as exc:  # noqa: BLE001
        result["error"] = f"Erro de TLS/HTTP ao contactar o endpoint: {exc!r}"
        return result

    try:
        root = ET.fromstring(text)
        ns = {"env": "http://schemas.xmlsoap.org/soap/envelope/"}
        fault = root.find(".//env:Fault", ns)
        if fault is not None:
            result["soap_fault_code"] = fault.findtext("faultcode")
            result["soap_fault_string"] = fault.findtext("faultstring")
    except Exception:  # noqa: BLE001
        pass

    return result


class EFaturasClient:
    """API pública de alto nível para faturas e séries."""

    def __init__(
        self,
        *,
        username: str,
        password: str,
        public_key_path: str | Path,
        client_cert_path: str | Path,
        client_key_path: str | Path | None = None,
        ca_cert_path: str | Path | None = None,
        environment: Environment | str = "prod",
        timeout: int | float = 30,
        faturas_endpoint: str | None = None,
        series_endpoint: str | None = None,
    ) -> None:
        self._ws_client = _WSClient(
            username=username,
            password=password,
            public_key_path=public_key_path,
            client_cert_path=client_cert_path,
            client_key_path=client_key_path,
            ca_cert_path=ca_cert_path,
            environment=environment,
            timeout=timeout,
        )
        self._faturas_endpoint = faturas_endpoint
        self._series_endpoint = series_endpoint

    # ---------- helpers internos ----------

    def _faturas_service(self):
        from .faturas import FaturasService

        return FaturasService(self._ws_client, endpoint=self._faturas_endpoint)

    def _series_service(self):
        from .series import SeriesService

        return SeriesService(self._ws_client, endpoint=self._series_endpoint)

    # ---------- conectividade ----------

    def test_connection(self, *, service: str = "faturas") -> EFaturasResult:
        service_norm = (service or "faturas").lower()
        try:
            info = test_connection(
                username=self._ws_client.username,
                password=self._ws_client.password,
                public_key_path=self._ws_client.public_key_path,
                client_cert_path=self._ws_client.client_cert_path,
                client_key_path=self._ws_client.client_key_path,
                ca_cert_path=self._ws_client.ca_cert_path,
                environment=self._ws_client.environment,
                timeout=self._ws_client.timeout,
                endpoint=self._faturas_endpoint
                if service_norm == "faturas"
                else self._series_endpoint,
                service=service_norm,
            )
        except Exception as exc:  # noqa: BLE001
            return EFaturasResult.from_exception(exc)

        ok = bool(info.get("username_token_ok")) and bool(info.get("tls_ok"))
        message = "Ligação efetuada com sucesso." if ok else "Falha ao testar ligação."
        return EFaturasResult(ok=ok, code=None, message=message, data=info)

    # ---------- validações internas ----------

    def _ensure_prod_has_software_cert(self, software_certificate_number: int | str) -> None:
        try:
            number = int(software_certificate_number)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("SoftwareCertificateNumber inválido.") from exc
        if self._ws_client.environment == Environment.PROD and number == 0:
            msg = (
                "Em produção, SoftwareCertificateNumber não pode ser 0. "
                "Defina o número emitido pela AT ou use ambiente de teste."
            )
            raise ValueError(msg)

    # ---------- faturas/obras/pagamentos ----------

    def register_invoice(
        self,
        *,
        efatura_md_version: str,
        audit_file_version: str,
        tax_registration_number: str | int,
        tax_entity: str,
        software_certificate_number: int,
        invoice_data: Mapping[str, Any],
        canal_registo: Mapping[str, Any] | None = None,
    ) -> EFaturasResult:
        try:
            from .faturas import RegisterInvoiceInput

            service = self._faturas_service()
            self._ensure_prod_has_software_cert(software_certificate_number)
            payload = RegisterInvoiceInput(
                efatura_md_version=efatura_md_version,
                audit_file_version=audit_file_version,
                tax_registration_number=tax_registration_number,
                tax_entity=tax_entity,
                software_certificate_number=software_certificate_number,
                invoice_data=invoice_data,
                canal_registo=canal_registo,
            )
            response = service.register_invoice(payload)
            return EFaturasResult.from_operation_response(response)
        except Exception as exc:  # noqa: BLE001
            return EFaturasResult.from_exception(exc)

    def change_invoice_status(
        self,
        *,
        efatura_md_version: str,
        tax_registration_number: str | int,
        invoice_header: Mapping[str, Any],
        invoice_status: Mapping[str, Any],
        canal_registo: Mapping[str, Any] | None = None,
    ) -> EFaturasResult:
        try:
            from .faturas import ChangeInvoiceStatusInput

            service = self._faturas_service()
            payload = ChangeInvoiceStatusInput(
                efatura_md_version=efatura_md_version,
                tax_registration_number=tax_registration_number,
                invoice_header=invoice_header,
                invoice_status=invoice_status,
                canal_registo=canal_registo,
            )
            response = service.change_invoice_status(payload)
            return EFaturasResult.from_operation_response(response)
        except Exception as exc:  # noqa: BLE001
            return EFaturasResult.from_exception(exc)

    def delete_invoice(
        self,
        *,
        efatura_md_version: str,
        tax_registration_number: str | int,
        reason: str,
        documents_list: Optional[list[Mapping[str, Any]]] = None,
        date_range: Optional[Mapping[str, Any]] = None,
        canal_registo: Mapping[str, Any] | None = None,
    ) -> EFaturasResult:
        try:
            from .faturas import DeleteInvoiceInput

            service = self._faturas_service()
            payload = DeleteInvoiceInput(
                efatura_md_version=efatura_md_version,
                tax_registration_number=tax_registration_number,
                reason=reason,
                documents_list=documents_list,
                date_range=date_range,
                canal_registo=canal_registo,
            )
            response = service.delete_invoice(payload)
            return EFaturasResult.from_operation_response(response)
        except Exception as exc:  # noqa: BLE001
            return EFaturasResult.from_exception(exc)

    def register_work(
        self,
        *,
        efatura_md_version: str,
        audit_file_version: str,
        tax_registration_number: str | int,
        tax_entity: str,
        software_certificate_number: int,
        work_data: Mapping[str, Any],
        canal_registo: Mapping[str, Any] | None = None,
    ) -> EFaturasResult:
        try:
            from .faturas import RegisterWorkInput

            service = self._faturas_service()
            self._ensure_prod_has_software_cert(software_certificate_number)
            payload = RegisterWorkInput(
                efatura_md_version=efatura_md_version,
                audit_file_version=audit_file_version,
                tax_registration_number=tax_registration_number,
                tax_entity=tax_entity,
                software_certificate_number=software_certificate_number,
                work_data=work_data,
                canal_registo=canal_registo,
            )
            response = service.register_work(payload)
            return EFaturasResult.from_operation_response(response)
        except Exception as exc:  # noqa: BLE001
            return EFaturasResult.from_exception(exc)

    def change_work_status(
        self,
        *,
        efatura_md_version: str,
        tax_registration_number: str | int,
        work_header: Mapping[str, Any],
        work_status: Mapping[str, Any],
        canal_registo: Mapping[str, Any] | None = None,
    ) -> EFaturasResult:
        try:
            from .faturas import ChangeWorkStatusInput

            service = self._faturas_service()
            payload = ChangeWorkStatusInput(
                efatura_md_version=efatura_md_version,
                tax_registration_number=tax_registration_number,
                work_header=work_header,
                work_status=work_status,
                canal_registo=canal_registo,
            )
            response = service.change_work_status(payload)
            return EFaturasResult.from_operation_response(response)
        except Exception as exc:  # noqa: BLE001
            return EFaturasResult.from_exception(exc)

    def delete_work(
        self,
        *,
        efatura_md_version: str,
        tax_registration_number: str | int,
        reason: str,
        documents_list: Optional[list[Mapping[str, Any]]] = None,
        date_range: Optional[Mapping[str, Any]] = None,
        canal_registo: Mapping[str, Any] | None = None,
    ) -> EFaturasResult:
        try:
            from .faturas import DeleteWorkInput

            service = self._faturas_service()
            payload = DeleteWorkInput(
                efatura_md_version=efatura_md_version,
                tax_registration_number=tax_registration_number,
                reason=reason,
                documents_list=documents_list,
                date_range=date_range,
                canal_registo=canal_registo,
            )
            response = service.delete_work(payload)
            return EFaturasResult.from_operation_response(response)
        except Exception as exc:  # noqa: BLE001
            return EFaturasResult.from_exception(exc)

    def register_payment(
        self,
        *,
        efatura_md_version: str,
        audit_file_version: str,
        tax_registration_number: str | int,
        tax_entity: str,
        software_certificate_number: int,
        payment_data: Mapping[str, Any],
        canal_registo: Mapping[str, Any] | None = None,
    ) -> EFaturasResult:
        try:
            from .faturas import RegisterPaymentInput

            service = self._faturas_service()
            self._ensure_prod_has_software_cert(software_certificate_number)
            payload = RegisterPaymentInput(
                efatura_md_version=efatura_md_version,
                audit_file_version=audit_file_version,
                tax_registration_number=tax_registration_number,
                tax_entity=tax_entity,
                software_certificate_number=software_certificate_number,
                payment_data=payment_data,
                canal_registo=canal_registo,
            )
            response = service.register_payment(payload)
            return EFaturasResult.from_operation_response(response)
        except Exception as exc:  # noqa: BLE001
            return EFaturasResult.from_exception(exc)

    def change_payment_status(
        self,
        *,
        efatura_md_version: str,
        tax_registration_number: str | int,
        payment_header: Mapping[str, Any],
        payment_status: Mapping[str, Any],
        canal_registo: Mapping[str, Any] | None = None,
    ) -> EFaturasResult:
        try:
            from .faturas import ChangePaymentStatusInput

            service = self._faturas_service()
            payload = ChangePaymentStatusInput(
                efatura_md_version=efatura_md_version,
                tax_registration_number=tax_registration_number,
                payment_header=payment_header,
                payment_status=payment_status,
                canal_registo=canal_registo,
            )
            response = service.change_payment_status(payload)
            return EFaturasResult.from_operation_response(response)
        except Exception as exc:  # noqa: BLE001
            return EFaturasResult.from_exception(exc)

    def delete_payment(
        self,
        *,
        efatura_md_version: str,
        tax_registration_number: str | int,
        reason: str,
        documents_list: Optional[list[Mapping[str, Any]]] = None,
        date_range: Optional[Mapping[str, Any]] = None,
        canal_registo: Mapping[str, Any] | None = None,
    ) -> EFaturasResult:
        try:
            from .faturas import DeletePaymentInput

            service = self._faturas_service()
            payload = DeletePaymentInput(
                efatura_md_version=efatura_md_version,
                tax_registration_number=tax_registration_number,
                reason=reason,
                documents_list=documents_list,
                date_range=date_range,
                canal_registo=canal_registo,
            )
            response = service.delete_payment(payload)
            return EFaturasResult.from_operation_response(response)
        except Exception as exc:  # noqa: BLE001
            return EFaturasResult.from_exception(exc)

    # ---------- séries ----------

    def create_series(
        self,
        *,
        serie: str,
        tipo_serie: str,
        classe_doc: str,
        tipo_doc: str,
        num_inicial_seq: int,
        data_inicio: Any,
        num_cert_sw: int | str,
        meio_processamento: str,
    ) -> EFaturasResult:
        try:
            from .series import CreateSeriesInput

            service = self._series_service()
            payload = CreateSeriesInput(
                serie=serie,
                tipo_serie=tipo_serie,
                classe_doc=classe_doc,
                tipo_doc=tipo_doc,
                num_inicial_seq=num_inicial_seq,
                data_inicio=data_inicio,
                num_cert_sw=num_cert_sw,
                meio_processamento=meio_processamento,
            )
            result = service.create_series(payload)
            return EFaturasResult.from_series_operation_result(result)
        except Exception as exc:  # noqa: BLE001
            return EFaturasResult.from_exception(exc)

    def finalize_series(
        self,
        *,
        serie: str,
        classe_doc: str,
        tipo_doc: str,
        codigo_validacao: str,
        seq_ultimo_doc_emitido: int,
        justificacao: str | None = None,
    ) -> EFaturasResult:
        try:
            from .series import FinalizeSeriesInput

            service = self._series_service()
            payload = FinalizeSeriesInput(
                serie=serie,
                classe_doc=classe_doc,
                tipo_doc=tipo_doc,
                codigo_validacao=codigo_validacao,
                seq_ultimo_doc_emitido=seq_ultimo_doc_emitido,
                justificacao=justificacao,
            )
            result = service.close_series(payload)
            return EFaturasResult.from_series_operation_result(result)
        except Exception as exc:  # noqa: BLE001
            return EFaturasResult.from_exception(exc)

    def cancel_series(
        self,
        *,
        serie: str,
        classe_doc: str,
        tipo_doc: str,
        codigo_validacao: str,
        motivo: str,
        declaracao_nao_emissao: bool = True,
    ) -> EFaturasResult:
        try:
            from .series import CancelSeriesInput

            service = self._series_service()
            payload = CancelSeriesInput(
                serie=serie,
                classe_doc=classe_doc,
                tipo_doc=tipo_doc,
                codigo_validacao=codigo_validacao,
                motivo=motivo,
                declaracao_nao_emissao=declaracao_nao_emissao,
            )
            result = service.cancel_series(payload)
            return EFaturasResult.from_series_operation_result(result)
        except Exception as exc:  # noqa: BLE001
            return EFaturasResult.from_exception(exc)

    def list_series(
        self,
        *,
        serie: str | None = None,
        tipo_serie: str | None = None,
        classe_doc: str | None = None,
        tipo_doc: str | None = None,
        codigo_validacao: str | None = None,
        data_registo_de: Any | None = None,
        data_registo_ate: Any | None = None,
        estado: str | None = None,
        meio_processamento: str | None = None,
    ) -> EFaturasResult:
        try:
            from .series import SeriesFilter

            service = self._series_service()
            filters = SeriesFilter(
                serie=serie,
                tipo_serie=tipo_serie,
                classe_doc=classe_doc,
                tipo_doc=tipo_doc,
                codigo_validacao=codigo_validacao,
                data_registo_de=data_registo_de,
                data_registo_ate=data_registo_ate,
                estado=estado,
                meio_processamento=meio_processamento,
            )
            result = service.list_series(filters)
            return EFaturasResult.from_series_list_result(result)
        except Exception as exc:  # noqa: BLE001
            return EFaturasResult.from_exception(exc)
