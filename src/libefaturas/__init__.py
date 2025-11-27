"""API pública e estável do pacote ``libefaturas``.

O módulo raiz expõe apenas a interface de alto nível (`EFaturasClient` e
`EFaturasResult`) e a versão do pacote. Todo o resto (serviços SOAP, payloads
ou dataclasses internas) é considerado detalhe de implementação.
"""

from .__about__ import __version__
from .client import EFaturasClient, EFaturasResult

__all__ = ["__version__", "EFaturasClient", "EFaturasResult"]
