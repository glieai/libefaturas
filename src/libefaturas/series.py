"""Séries do webservice SeriesWS da AT."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from .client import EFaturasClient


__all__ = [
    "CreateSeriesInput",
    "FinalizeSeriesInput",
    "CancelSeriesInput",
    "Series",
    "SeriesFilter",
    "OperationResult",
    "SeriesOperationResult",
    "SeriesListResult",
    "SeriesError",
    "SeriesService",
]


@dataclass
class CreateSeriesInput:
    serie: str
    tipo_serie: str
    classe_doc: str
    tipo_doc: str
    num_inicial_seq: int
    data_inicio: date
    num_cert_sw: int | str
    meio_processamento: str


@dataclass
class FinalizeSeriesInput:
    serie: str
    classe_doc: str
    tipo_doc: str
    codigo_validacao: str
    seq_ultimo_doc_emitido: int
    justificacao: Optional[str] = None


@dataclass
class CancelSeriesInput:
    serie: str
    classe_doc: str
    tipo_doc: str
    codigo_validacao: str
    motivo: str
    declaracao_nao_emissao: bool = True


@dataclass
class Series:
    serie: str
    codigo_validacao: Optional[str] = None
    tipo_serie: Optional[str] = None
    classe_doc: Optional[str] = None
    tipo_doc: Optional[str] = None
    estado: Optional[str] = None
    num_inicial_seq: Optional[int] = None
    num_final_seq: Optional[int] = None
    data_inicio: Optional[date] = None
    seq_ultimo_doc_emitido: Optional[int] = None
    meio_processamento: Optional[str] = None
    num_cert_sw: Optional[str] = None
    data_registo: Optional[date] = None
    motivo_estado: Optional[str] = None
    justificacao: Optional[str] = None
    data_estado: Optional[datetime] = None
    nif_comunicou: Optional[str] = None


@dataclass
class SeriesFilter:
    serie: Optional[str] = None
    tipo_serie: Optional[str] = None
    classe_doc: Optional[str] = None
    tipo_doc: Optional[str] = None
    codigo_validacao: Optional[str] = None
    data_registo_de: Optional[date] = None
    data_registo_ate: Optional[date] = None
    estado: Optional[str] = None
    meio_processamento: Optional[str] = None


@dataclass
class OperationResult:
    code: Optional[int]
    message: str

    @property
    def ok(self) -> bool:
        return self.code == 0


@dataclass
class SeriesOperationResult:
    series: Optional[Series]
    result: OperationResult


@dataclass
class SeriesListResult:
    series: list[Series]
    result: OperationResult


class SeriesError(Exception):
    """Erros específicos do módulo de séries."""


class SeriesService:
    _SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
    _AT_NS = "http://at.gov.pt/"
    _NS = {"soap": _SOAP_NS, "at": _AT_NS}

    def __init__(
        self,
        client: EFaturasClient,
        *,
        endpoint: Optional[str] = None,
    ) -> None:
        self._client = client
        self._endpoint_override = endpoint
        self._last_response_text: str | None = None

    # ---------- helpers internos ----------

    @staticmethod
    def _format_date(value: date) -> str:
        return value.strftime("%Y-%m-%d")

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        if value.tzinfo is None:
            return value.replace(microsecond=0).isoformat()
        return value.astimezone(value.tzinfo).replace(microsecond=0).isoformat()

    @staticmethod
    def _serialize_value(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, datetime):
            return SeriesService._format_datetime(value)
        if isinstance(value, date):
            return SeriesService._format_date(value)
        return str(value)

    @staticmethod
    def _parse_int(text: Optional[str]) -> Optional[int]:
        if not text:
            return None
        try:
            return int(text)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_date(text: Optional[str]) -> Optional[date]:
        if not text:
            return None
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
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

    def _render_body(self, action: str, payload: list[tuple[str, Optional[str]]]) -> str:
        inner = "".join(
            f"<{tag}>{escape(value)}</{tag}>"
            for tag, value in payload
            if value is not None
        )
        return (
            "<S:Body>"
            f'<{action} xmlns="{self._AT_NS}">'
            f"{inner}"
            f"</{action}>"
            "</S:Body>"
        )

    def _call_operation(
        self,
        action: str,
        payload: list[tuple[str, Optional[str]]],
    ) -> ET.Element:
        body_xml = self._render_body(action, payload)
        response = self._client.post(
            service="series",
            body_xml=body_xml,
            endpoint=self._endpoint_override,
        )
        self._last_request_xml = self._client.build_envelope_xml(body_xml)
        response_text = response.text
        self._last_response_text = response_text
        try:
            element = self._extract_response_element(response_text, action)
        except SeriesError as exc:
            if response.status_code != 200:
                raise SeriesError(f"{exc} (HTTP {response.status_code})") from exc
            raise
        if response.status_code != 200:
            snippet = response_text[:500]
            raise SeriesError(
                f"HTTP {response.status_code} ao chamar {action}: {snippet}"
            )
        return element

    def _extract_response_element(self, xml: str, action: str) -> ET.Element:
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as exc:
            raise SeriesError(f"Resposta XML inválida: {exc}") from exc

        fault = root.find(".//soap:Fault", self._NS)
        if fault is not None:
            code = fault.findtext("faultcode") or ""
            message = fault.findtext("faultstring") or ""
            raise SeriesError(f"SOAP Fault em {action}: {code} - {message}")

        element = root.find(f".//at:{action}Response", self._NS)
        if element is None:
            raise SeriesError(
                f"Elemento {action}Response não encontrado na resposta SOAP."
            )
        return element

    @staticmethod
    def _tag_matches(node: ET.Element, name: str) -> bool:
        raw = node.tag or ""
        if raw == name:
            return True
        if raw.endswith(f"}}{name}"):
            return True
        return False

    def _find(self, parent: ET.Element, tag: str) -> Optional[ET.Element]:
        node = parent.find(f"at:{tag}", self._NS)
        if node is None:
            node = parent.find(tag)
        if node is None:
            for child in parent:
                if isinstance(child.tag, str) and self._tag_matches(child, tag):
                    return child
        return node

    def _findall(self, parent: ET.Element, tag: str) -> list[ET.Element]:
        nodes = parent.findall(f"at:{tag}", self._NS)
        if not nodes:
            nodes = parent.findall(tag)
        if not nodes:
            nodes = parent.findall(f".//at:{tag}", self._NS)
        if not nodes:
            nodes = parent.findall(f".//{tag}")
        if not nodes:
            nodes = [
                child
                for child in parent.iter()
                if isinstance(child.tag, str) and self._tag_matches(child, tag)
            ]
        return nodes

    def _findtext(self, parent: ET.Element, tag: str) -> Optional[str]:
        node = self._find(parent, tag)
        return node.text if node is not None else None

    def _parse_series(self, element: ET.Element) -> Series:
        def text(name: str) -> Optional[str]:
            return self._findtext(element, name)

        num_inicial_seq = self._parse_int(text("numInicialSeq"))
        num_final_seq = self._parse_int(text("numFinalSeq"))
        seq_ultimo = self._parse_int(text("seqUltimoDocEmitido"))

        return Series(
            serie=text("serie") or "",
            codigo_validacao=text("codValidacaoSerie"),
            tipo_serie=text("tipoSerie"),
            classe_doc=text("classeDoc"),
            tipo_doc=text("tipoDoc"),
            estado=text("estado"),
            num_inicial_seq=num_inicial_seq,
            num_final_seq=num_final_seq,
            data_inicio=self._parse_date(text("dataInicioPrevUtiliz")),
            seq_ultimo_doc_emitido=seq_ultimo,
            meio_processamento=text("meioProcessamento"),
            num_cert_sw=text("numCertSWFatur"),
            data_registo=self._parse_date(text("dataRegisto")),
            motivo_estado=text("motivoEstado"),
            justificacao=text("justificacao"),
            data_estado=self._parse_datetime(text("dataEstado")),
            nif_comunicou=text("nifComunicou"),
        )

    def _parse_operation_result(self, element: Optional[ET.Element]) -> OperationResult:
        if element is None:
            return OperationResult(code=None, message="")
        code = self._parse_int(self._findtext(element, "codResultOper"))
        message = self._findtext(element, "msgResultOper") or ""
        return OperationResult(code=code, message=message)

    def _parse_series_operation(
        self,
        parent: ET.Element,
        child_tag: str,
    ) -> SeriesOperationResult:
        container = self._find(parent, child_tag)
        if container is None:
            raise SeriesError(f"Elemento {child_tag} não encontrado na resposta SOAP.")

        info_element = self._find(container, "infoSerie")
        series = self._parse_series(info_element) if info_element is not None else None
        result = self._parse_operation_result(self._find(container, "infoResultOper"))
        return SeriesOperationResult(series=series, result=result)

    def _parse_series_list(self, parent: ET.Element) -> SeriesListResult:
        container = self._find(parent, "consultarSeriesResp")
        if container is None:
            # fallback: já vimos respostas sem o nó wrapper, usar o parent
            container = parent

        series_nodes = self._findall(container, "infoSerie")
        if not series_nodes and container is parent:
            # último recurso: procurar globalmente
            series_nodes = self._findall(parent, "infoSerie")
            container_for_result = parent
        else:
            container_for_result = container

        series = [self._parse_series(node) for node in series_nodes]
        result_node = self._find(container_for_result, "infoResultOper")
        if result_node is None:
            result_node = self._find(parent, "infoResultOper")
        result = self._parse_operation_result(result_node)
        if not series and result.code is None:
            raise SeriesError(
                "Elemento consultarSeriesResp não encontrado na resposta SOAP."
            )
        return SeriesListResult(series=series, result=result)

    # ---------- API pública ----------

    def create_series(self, data: CreateSeriesInput) -> SeriesOperationResult:
        payload = [
            ("serie", self._serialize_value(data.serie)),
            ("tipoSerie", self._serialize_value(data.tipo_serie)),
            ("classeDoc", self._serialize_value(data.classe_doc)),
            ("tipoDoc", self._serialize_value(data.tipo_doc)),
            ("numInicialSeq", self._serialize_value(data.num_inicial_seq)),
            ("dataInicioPrevUtiliz", self._serialize_value(data.data_inicio)),
            ("numCertSWFatur", self._serialize_value(data.num_cert_sw)),
            ("meioProcessamento", self._serialize_value(data.meio_processamento)),
        ]
        response = self._call_operation("registarSerie", payload)
        return self._parse_series_operation(response, "registarSerieResp")

    def list_series(self, flt: SeriesFilter | None = None) -> SeriesListResult:
        payload: list[tuple[str, Optional[str]]] = []
        if flt:
            payload.extend(
                [
                    ("serie", self._serialize_value(flt.serie)),
                    ("tipoSerie", self._serialize_value(flt.tipo_serie)),
                    ("classeDoc", self._serialize_value(flt.classe_doc)),
                    ("tipoDoc", self._serialize_value(flt.tipo_doc)),
                    ("codValidacaoSerie", self._serialize_value(flt.codigo_validacao)),
                    ("dataRegistoDe", self._serialize_value(flt.data_registo_de)),
                    ("dataRegistoAte", self._serialize_value(flt.data_registo_ate)),
                    ("estado", self._serialize_value(flt.estado)),
                    (
                        "meioProcessamento",
                        self._serialize_value(flt.meio_processamento),
                    ),
                ]
            )
        response = self._call_operation("consultarSeries", payload)
        return self._parse_series_list(response)

    def close_series(self, data: FinalizeSeriesInput) -> SeriesOperationResult:
        payload = [
            ("serie", self._serialize_value(data.serie)),
            ("classeDoc", self._serialize_value(data.classe_doc)),
            ("tipoDoc", self._serialize_value(data.tipo_doc)),
            ("codValidacaoSerie", self._serialize_value(data.codigo_validacao)),
            (
                "seqUltimoDocEmitido",
                self._serialize_value(data.seq_ultimo_doc_emitido),
            ),
            ("justificacao", self._serialize_value(data.justificacao)),
        ]
        response = self._call_operation("finalizarSerie", payload)
        return self._parse_series_operation(response, "finalizarSerieResp")

    def cancel_series(self, data: CancelSeriesInput) -> SeriesOperationResult:
        payload = [
            ("serie", self._serialize_value(data.serie)),
            ("classeDoc", self._serialize_value(data.classe_doc)),
            ("tipoDoc", self._serialize_value(data.tipo_doc)),
            ("codValidacaoSerie", self._serialize_value(data.codigo_validacao)),
            ("motivo", self._serialize_value(data.motivo)),
            (
                "declaracaoNaoEmissao",
                self._serialize_value(data.declaracao_nao_emissao),
            ),
        ]
        response = self._call_operation("anularSerie", payload)
        return self._parse_series_operation(response, "anularSerieResp")
