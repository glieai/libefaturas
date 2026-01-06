"""API pública e estável do pacote ``libefaturas``.

O módulo raiz expõe a interface de alto nível (`EFaturasClient` e
`EFaturasResult`), exceções personalizadas, utilitários PT e a versão do pacote.

Para funcionalidades de assinatura SAF-T, use:
    from libefaturas.security import gerar_hash_fatura

Para utilitários de QR code e formatação PT:
    from libefaturas.pt_utils import build_qr_payload, extract_hash_chars
"""

from .__about__ import __version__
from .client import EFaturasClient, EFaturasResult
from .exceptions import (
    EFaturasAuthError,
    EFaturasConnectionError,
    EFaturasError,
    EFaturasKeyError,
    EFaturasRetryError,
    EFaturasSOAPError,
    EFaturasValidationError,
)
from .retry import RetryConfig

__all__ = [
    # Version
    "__version__",
    # Client
    "EFaturasClient",
    "EFaturasResult",
    # Exceptions
    "EFaturasError",
    "EFaturasAuthError",
    "EFaturasConnectionError",
    "EFaturasKeyError",
    "EFaturasRetryError",
    "EFaturasSOAPError",
    "EFaturasValidationError",
    # Configuration
    "RetryConfig",
]
