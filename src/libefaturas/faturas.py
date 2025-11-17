from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from .client import test_connection  # mais tarde vamos ter um client “a sério” aqui


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


class SeriesService:
    def __init__(self, client):
        self._client = client

    def create_series(self, data: CreateSeriesInput) -> Series:
        """Chama registarSerie no SeriesWS."""
        raise NotImplementedError

    def list_series(self, flt: SeriesFilter | None = None) -> list[Series]:
        """Chama consultarSeries no SeriesWS."""
        raise NotImplementedError

    def close_series(self, codigo_validacao: str) -> Series:
        """Chama finalizarSerie no SeriesWS."""
        raise NotImplementedError

    def cancel_series(self, codigo_validacao: str, reason: str | None = None) -> Series:
        """Chama anularSerie no SeriesWS."""
        raise NotImplementedError
