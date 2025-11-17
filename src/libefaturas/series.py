"""Séries do webservice SeriesWS da AT."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, List
import xml.etree.ElementTree as ET

from .client import EFaturasClient


__all__ = [
    "CreateSeriesInput",
    "Series",
    "SeriesFilter",
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
    num_cert_sw: str
    meio_processamento: str
    # aqui depois podes acrescentar outros campos opcionais do WSDL:
    # ex.: local_execucao, numUltDocEmitido, etc.


@dataclass
class Series:
    codigo_validacao: str
    serie: str
    tipo_serie: str
    classe_doc: str
    tipo_doc: str
    estado: str
    num_inicial_seq: int
    num_final_seq: Optional[int]
    data_inicio: date
    data_fim: Optional[date]


@dataclass
class SeriesFilter:
    classe_doc: Optional[str] = None
    tipo_doc: Optional[str] = None
    serie: Optional[str] = None
    estado: Optional[str] = None


class SeriesError(Exception):
    """Erros específicos do módulo de séries."""


class SeriesService:
    def __init__(
        self,
        client: EFaturasClient,
        *,
        endpoint: Optional[str] = None,
    ) -> None:
        self._client = client
        self._endpoint_override = endpoint

    # ---------- helpers internos ----------

    @staticmethod
    def _format_date(d: date) -> str:
        return d.strftime("%Y-%m-%d")

    @staticmethod
    def _parse_date(text: Optional[str]) -> Optional[date]:
        if not text:
            return None
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return None

    def _build_registar_serie_body(self, data: CreateSeriesInput) -> str:
        # nomes dos elementos alinhados com o que é típico no SeriesWS:
        # registarSerie -> serie, tipoSerie, classeDoc, tipoDoc, numInicialSeq,
        # dataInicioPrevUtiliz, numCertSWFatur, meioProcessamento, ...
        return (
            "<S:Body>"
            '<registarSerie xmlns="http://at.gov.pt/">'
            f"<serie>{data.serie}</serie>"
            f"<tipoSerie>{data.tipo_serie}</tipoSerie>"
            f"<classeDoc>{data.classe_doc}</classeDoc>"
            f"<tipoDoc>{data.tipo_doc}</tipoDoc>"
            f"<numInicialSeq>{data.num_inicial_seq}</numInicialSeq>"
            f"<dataInicioPrevUtiliz>{self._format_date(data.data_inicio)}</dataInicioPrevUtiliz>"
            f"<numCertSWFatur>{data.num_cert_sw}</numCertSWFatur>"
            f"<meioProcessamento>{data.meio_processamento}</meioProcessamento>"
            "</registarSerie>"
            "</S:Body>"
        )

    def _parse_registar_serie_response(self, xml: str) -> Series:
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as exc:
            raise SeriesError(f"Resposta XML inválida: {exc}") from exc

        # Verificar SOAP Fault
        fault = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Fault")
        if fault is not None:
            code = fault.findtext("faultcode") or ""
            msg = fault.findtext("faultstring") or ""
            raise SeriesError(f"SOAP Fault em registarSerie: {code} - {msg}")

        ns = {"at": "http://at.gov.pt/"}
        resp = root.find(".//at:registarSerieResponse", ns)
        if resp is None:
            # dependendo do WSDL, o nome pode variar; isto é o default
            raise SeriesError("Elemento registarSerieResponse não encontrado na resposta.")

        def t(name: str) -> Optional[str]:
            return resp.findtext(f"at:{name}", default=None, namespaces=ns)

        codigo_validacao = t("codigoValidacaoSerie") or ""
        serie = t("serie") or ""
        tipo_serie = t("tipoSerie") or ""
        classe_doc = t("classeDoc") or ""
        tipo_doc = t("tipoDoc") or ""
        estado = t("estado") or ""
        num_inicial_seq_txt = t("numInicialSeq")
        num_final_seq_txt = t("numFinalSeq")
        data_inicio_txt = t("dataInicioPrevUtiliz")
        data_fim_txt = t("dataFimUtiliz")

        try:
            num_inicial_seq = int(num_inicial_seq_txt) if num_inicial_seq_txt else 0
        except ValueError:
            num_inicial_seq = 0

        try:
            num_final_seq = int(num_final_seq_txt) if num_final_seq_txt else None
        except ValueError:
            num_final_seq = None

        data_inicio = self._parse_date(data_inicio_txt) or date.today()
        data_fim = self._parse_date(data_fim_txt)

        return Series(
            codigo_validacao=codigo_validacao,
            serie=serie,
            tipo_serie=tipo_serie,
            classe_doc=classe_doc,
            tipo_doc=tipo_doc,
            estado=estado,
            num_inicial_seq=num_inicial_seq,
            num_final_seq=num_final_seq,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )

    # ---------- API pública ----------

    def create_series(self, data: CreateSeriesInput) -> Series:
        """Chama registarSerie no SeriesWS e devolve o objeto Series normalizado."""
        body_xml = self._build_registar_serie_body(data)
        response = self._client.post(
            service="series",
            body_xml=body_xml,
            endpoint=self._endpoint_override,
        )

        if response.status_code != 200:
            raise SeriesError(
                f"HTTP {response.status_code} ao chamar registarSerie: {response.text[:500]}"
            )

        return self._parse_registar_serie_response(response.text)

    def list_series(self, flt: SeriesFilter | None = None) -> List[Series]:
        """Chama consultarSeries no SeriesWS (por implementar)."""
        raise NotImplementedError

    def close_series(self, codigo_validacao: str) -> Series:
        """Chama finalizarSerie no SeriesWS (por implementar)."""
        raise NotImplementedError

    def cancel_series(self, codigo_validacao: str, reason: str | None = None) -> Series:
        """Chama anularSerie no SeriesWS (por implementar)."""
        raise NotImplementedError
