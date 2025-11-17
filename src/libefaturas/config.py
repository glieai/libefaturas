"""Configuração de endpoints dos webservices da AT."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Environment(str, Enum):
    TEST = "test"
    PROD = "prod"


@dataclass(frozen=True)
class ServiceEndpoints:
    faturas: str
    series: str


ENDPOINTS: dict[Environment, ServiceEndpoints] = {
    Environment.TEST: ServiceEndpoints(
        faturas="https://servicos.portaldasfinancas.gov.pt:700/fews/faturas",
        series="https://servicos.portaldasfinancas.gov.pt:722/SeriesWSService",
    ),
    Environment.PROD: ServiceEndpoints(
        faturas="https://servicos.portaldasfinancas.gov.pt:400/fews/faturas",
        series="https://servicos.portaldasfinancas.gov.pt:422/SeriesWSService",
    ),
}
