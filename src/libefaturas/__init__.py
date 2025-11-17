"""API pública exposta pelo pacote ``libefaturas``."""

from .__about__ import __version__
from .client import EFaturasClient, test_connection
from .security import EFaturasCredentials, UsernameToken
from .faturas import OperationResponse, FaturasError, FaturasService
from .series import (
    OperationResult,
    Series,
    SeriesError,
    SeriesFilter,
    SeriesListResult,
    SeriesOperationResult,
    SeriesService,
)

__all__ = [
    "__version__",
    "EFaturasClient",
    "test_connection",
    "EFaturasCredentials",
    "UsernameToken",
    "OperationResponse",
    "FaturasError",
    "FaturasService",
    "Series",
    "SeriesFilter",
    "OperationResult",
    "SeriesOperationResult",
    "SeriesListResult",
    "SeriesError",
    "SeriesService",
]
