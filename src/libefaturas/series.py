"""Séries do webservice SeriesWS da AT."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, ClassVar, Optional
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from .client import _WSClient


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
    _SERIE_MAX_LEN: ClassVar[int] = 35
    _CODIGOS_TIPO_SERIE: ClassVar[set[str]] = {"N", "F", "R"}
    _CODIGOS_CLASSE_DOC: ClassVar[set[str]] = {"SI", "MG", "WD", "PY"}
    _CODIGOS_TIPO_DOC: ClassVar[dict[str, set[str]]] = {
        "SI": {"FT", "FS", "FR", "ND", "NC", "VD", "TV", "AA", "DA"},
        "MG": {"GR", "GT", "GA", "GC", "GD"},
        "WD": {"FO", "NE", "DC", "OR"},
        "PY": {"RC", "RG", "RE", "CS", "LD", "RA", "RP"},
    }
    _CODIGOS_TIPO_DOC_TODOS: ClassVar[set[str]] = set().union(*_CODIGOS_TIPO_DOC.values())
    _CODIGO_MEIO_PROCESSAMENTO: ClassVar[set[str]] = {"PI", "PF", "OM"}

    def __post_init__(self) -> None:
        self.serie = self._validate_str(self.serie, "serie", max_length=self._SERIE_MAX_LEN)
        self.tipo_serie = self._validate_code(
            self.tipo_serie,
            "tipo_serie",
            expected_len=1,
            allowed=self._CODIGOS_TIPO_SERIE,
        )
        self.classe_doc = self._validate_code(
            self.classe_doc,
            "classe_doc",
            expected_len=2,
            allowed=self._CODIGOS_CLASSE_DOC,
        )
        self.tipo_doc = self._validate_tipo_doc(self.tipo_doc, self.classe_doc)
        self.num_inicial_seq = self._validate_int(
            self.num_inicial_seq,
            "num_inicial_seq",
            min_value=1,
            max_digits=25,
        )
        self.data_inicio = self._validate_date(self.data_inicio, "data_inicio")
        self.num_cert_sw = self._validate_num_cert_sw(self.num_cert_sw)
        self.meio_processamento = self._validate_code(
            self.meio_processamento,
            "meio_processamento",
            expected_len=2,
            allowed=self._CODIGO_MEIO_PROCESSAMENTO,
        )

    @staticmethod
    def _validate_str(value: str, field: str, *, max_length: int, min_length: int = 1) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string.")
        cleaned = value.strip()
        if len(cleaned) < min_length:
            raise ValueError(f"{field} must have at least {min_length} characters.")
        if len(cleaned) > max_length:
            raise ValueError(f"{field} must have at most {max_length} characters.")
        return cleaned

    @staticmethod
    def _validate_code(
        value: str,
        field: str,
        *,
        expected_len: int,
        allowed: set[str],
    ) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string.")
        cleaned = value.strip().upper()
        if len(cleaned) != expected_len:
            raise ValueError(f"{field} must have length {expected_len}.")
        if cleaned not in allowed:
            raise ValueError(f"{field} must be one of: {', '.join(sorted(allowed))}.")
        return cleaned

    def _validate_tipo_doc(self, value: str, classe_doc: str) -> str:
        if not isinstance(value, str):
            raise ValueError("tipo_doc must be a string.")
        cleaned = value.strip().upper()
        if len(cleaned) != 2:
            raise ValueError("tipo_doc must have length 2.")
        allowed_for_class = self._CODIGOS_TIPO_DOC.get(classe_doc)
        if allowed_for_class and cleaned not in allowed_for_class:
            allowed_txt = ", ".join(sorted(allowed_for_class))
            raise ValueError(f"tipo_doc must match classe_doc {classe_doc}: {allowed_txt}.")
        if cleaned not in self._CODIGOS_TIPO_DOC_TODOS:
            allowed_txt = ", ".join(sorted(self._CODIGOS_TIPO_DOC_TODOS))
            raise ValueError(f"tipo_doc must be one of: {allowed_txt}.")
        return cleaned

    @staticmethod
    def _validate_int(value: Any, field: str, *, min_value: int, max_digits: int) -> int:
        if isinstance(value, bool) or value is None:
            raise ValueError(f"{field} must be an integer.")
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be an integer.") from exc
        if number < min_value:
            raise ValueError(f"{field} must be >= {min_value}.")
        if len(str(abs(number))) > max_digits:
            raise ValueError(f"{field} must have at most {max_digits} digits.")
        return number

    @staticmethod
    def _validate_date(value: Any, field: str) -> date:
        if isinstance(value, datetime):
            return value.date()
        if not isinstance(value, date):
            raise ValueError(f"{field} must be a date.")
        return value

    def _validate_num_cert_sw(self, value: int | str) -> str | int:
        if isinstance(value, bool) or value is None:
            raise ValueError("num_cert_sw must be an integer with up to 4 digits.")
        if isinstance(value, int):
            if value < 0:
                raise ValueError("num_cert_sw must be >= 0.")
            if len(str(value)) > 4:
                raise ValueError("num_cert_sw must have at most 4 digits.")
            return value
        if not isinstance(value, str):
            raise ValueError("num_cert_sw must be an int or str of digits.")
        cleaned = value.strip()
        if not cleaned.isdigit():
            raise ValueError("num_cert_sw must contain only digits.")
        if len(cleaned) > 4:
            raise ValueError("num_cert_sw must have at most 4 digits.")
        return cleaned


@dataclass
class FinalizeSeriesInput:
    serie: str
    classe_doc: str
    tipo_doc: str
    codigo_validacao: str
    seq_ultimo_doc_emitido: int
    justificacao: Optional[str] = None
    _COD_VALIDACAO_LEN: ClassVar[int] = 8
    _JUSTIFICACAO_MAX_LEN: ClassVar[int] = 4000
    _CODIGOS_CLASSE_DOC: ClassVar[set[str]] = CreateSeriesInput._CODIGOS_CLASSE_DOC
    _CODIGOS_TIPO_DOC_TODOS: ClassVar[set[str]] = CreateSeriesInput._CODIGOS_TIPO_DOC_TODOS
    _CODIGOS_TIPO_DOC: ClassVar[dict[str, set[str]]] = CreateSeriesInput._CODIGOS_TIPO_DOC

    def __post_init__(self) -> None:
        if isinstance(self.seq_ultimo_doc_emitido, bool):
            raise ValueError("seq_ultimo_doc_emitido must be an integer.")
        try:
            seq_int = int(self.seq_ultimo_doc_emitido)
        except (TypeError, ValueError) as exc:
            raise ValueError("seq_ultimo_doc_emitido must be an integer.") from exc
        if seq_int < 1:
            raise ValueError(
                "seq_ultimo_doc_emitido must be >= 1. "
                "If a série não teve documentos emitidos, use anularSerie em vez de finalizarSerie."
            )
        if len(str(abs(seq_int))) > 25:
            raise ValueError("seq_ultimo_doc_emitido must have at most 25 digits.")
        self.seq_ultimo_doc_emitido = seq_int
        self.serie = CreateSeriesInput._validate_str(
            self.serie,
            "serie",
            max_length=CreateSeriesInput._SERIE_MAX_LEN,
        )
        self.classe_doc = CreateSeriesInput._validate_code(
            self.classe_doc,
            "classe_doc",
            expected_len=2,
            allowed=self._CODIGOS_CLASSE_DOC,
        )
        self.tipo_doc = self._validate_tipo_doc(self.tipo_doc)
        if not isinstance(self.codigo_validacao, str):
            raise ValueError("codigo_validacao must be a string.")
        cleaned_code = self.codigo_validacao.strip()
        if len(cleaned_code) != self._COD_VALIDACAO_LEN:
            raise ValueError("codigo_validacao must have length 8.")
        self.codigo_validacao = cleaned_code
        if self.justificacao is not None:
            if not isinstance(self.justificacao, str):
                raise ValueError("justificacao must be a string.")
            cleaned = self.justificacao.strip()
            if len(cleaned) > self._JUSTIFICACAO_MAX_LEN:
                raise ValueError("justificacao must have at most 4000 characters.")
            self.justificacao = cleaned or None

    def _validate_tipo_doc(self, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("tipo_doc must be a string.")
        cleaned = value.strip().upper()
        if len(cleaned) != 2:
            raise ValueError("tipo_doc must have length 2.")
        allowed_for_class = self._CODIGOS_TIPO_DOC.get(self.classe_doc)
        if allowed_for_class and cleaned not in allowed_for_class:
            allowed_txt = ", ".join(sorted(allowed_for_class))
            raise ValueError(f"tipo_doc must match classe_doc {self.classe_doc}: {allowed_txt}.")
        if cleaned not in self._CODIGOS_TIPO_DOC_TODOS:
            allowed_txt = ", ".join(sorted(self._CODIGOS_TIPO_DOC_TODOS))
            raise ValueError(f"tipo_doc must be one of: {allowed_txt}.")
        return cleaned


@dataclass
class CancelSeriesInput:
    serie: str
    classe_doc: str
    tipo_doc: str
    codigo_validacao: str
    motivo: str
    declaracao_nao_emissao: bool = True
    _COD_VALIDACAO_LEN: ClassVar[int] = FinalizeSeriesInput._COD_VALIDACAO_LEN
    _MOTIVO_CANCELAMENTO: ClassVar[set[str]] = {"ER"}
    _CODIGOS_CLASSE_DOC: ClassVar[set[str]] = CreateSeriesInput._CODIGOS_CLASSE_DOC
    _CODIGOS_TIPO_DOC_TODOS: ClassVar[set[str]] = CreateSeriesInput._CODIGOS_TIPO_DOC_TODOS
    _CODIGOS_TIPO_DOC: ClassVar[dict[str, set[str]]] = CreateSeriesInput._CODIGOS_TIPO_DOC

    def __post_init__(self) -> None:
        self.serie = CreateSeriesInput._validate_str(
            self.serie,
            "serie",
            max_length=CreateSeriesInput._SERIE_MAX_LEN,
        )
        self.classe_doc = CreateSeriesInput._validate_code(
            self.classe_doc,
            "classe_doc",
            expected_len=2,
            allowed=self._CODIGOS_CLASSE_DOC,
        )
        self.tipo_doc = self._validate_tipo_doc(self.tipo_doc)
        self.codigo_validacao = self._validate_codigo_validacao(self.codigo_validacao)
        self.motivo = self._validate_motivo(self.motivo)
        if not isinstance(self.declaracao_nao_emissao, bool):
            raise ValueError("declaracao_nao_emissao must be a boolean.")

    def _validate_codigo_validacao(self, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("codigo_validacao must be a string.")
        cleaned = value.strip()
        if len(cleaned) != self._COD_VALIDACAO_LEN:
            raise ValueError("codigo_validacao must have length 8.")
        return cleaned

    def _validate_motivo(self, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("motivo must be a string.")
        cleaned = value.strip().upper()
        if len(cleaned) != 2:
            raise ValueError("motivo must have length 2.")
        if cleaned not in self._MOTIVO_CANCELAMENTO:
            allowed_txt = ", ".join(sorted(self._MOTIVO_CANCELAMENTO))
            raise ValueError(f"motivo must be one of: {allowed_txt}.")
        return cleaned

    def _validate_tipo_doc(self, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("tipo_doc must be a string.")
        cleaned = value.strip().upper()
        if len(cleaned) != 2:
            raise ValueError("tipo_doc must have length 2.")
        allowed_for_class = self._CODIGOS_TIPO_DOC.get(self.classe_doc)
        if allowed_for_class and cleaned not in allowed_for_class:
            allowed_txt = ", ".join(sorted(allowed_for_class))
            raise ValueError(f"tipo_doc must match classe_doc {self.classe_doc}: {allowed_txt}.")
        if cleaned not in self._CODIGOS_TIPO_DOC_TODOS:
            allowed_txt = ", ".join(sorted(self._CODIGOS_TIPO_DOC_TODOS))
            raise ValueError(f"tipo_doc must be one of: {allowed_txt}.")
        return cleaned


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
    # SeriesWS devolve 2xxx quando a operação é aceite, apesar do manual dizer 0.
    _SUCCESS_CODES: ClassVar[set[int]] = {0}

    @property
    def ok(self) -> bool:
        if self.code is None:
            return False
        if self.code in self._SUCCESS_CODES:
            return True
        return 2000 <= self.code < 3000


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
        client: _WSClient,
        *,
        endpoint: Optional[str] = None,
    ) -> None:
        self._client = client
        self._endpoint_override = endpoint
        self._last_request_xml: str | None = None
        self._last_response_text: str | None = None

    def _attach_last_exchange_to_exception(self, exc: SeriesError) -> SeriesError:
        """Annotate an exception with the last SOAP request/response snippets."""
        try:
            if not getattr(exc, "last_request_xml", None):
                exc.last_request_xml = self._last_request_xml or getattr(
                    getattr(self, "_client", None),
                    "_last_request_xml",
                    None,
                )
            if not getattr(exc, "last_response_text", None):
                exc.last_response_text = self._last_response_text
        except Exception:  # noqa: BLE001
            pass
        return exc

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
            f'<{tag} xmlns="">{escape(value)}</{tag}>'
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
        # Store the full envelope before the HTTP call so we can log it even if the request crashes.
        self._last_request_xml = self._client.build_envelope_xml(body_xml)
        response = self._client.post(
            service="series",
            body_xml=body_xml,
            endpoint=self._endpoint_override,
        )
        response_text = response.text
        self._last_response_text = response_text
        try:
            element = self._extract_response_element(response_text, action)
        except SeriesError as exc:
            exc = self._attach_last_exchange_to_exception(exc)
            if response.status_code != 200:
                new_exc = SeriesError(f"{exc} (HTTP {response.status_code})")
                self._attach_last_exchange_to_exception(new_exc)
                raise new_exc from exc
            raise exc
        if response.status_code != 200:
            snippet = response_text[:500]
            exc = SeriesError(
                f"HTTP {response.status_code} ao chamar {action}: {snippet}"
            )
            self._attach_last_exchange_to_exception(exc)
            raise exc
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
