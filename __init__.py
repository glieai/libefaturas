"""
API pública da biblioteca efatura_auth.

Uso típico:

    from efatura_auth import (
        EFaturaCredentials,
        build_username_token,
        build_security_header_xml,
    )
"""

from ._core import (
    EFaturaCredentials,
    UsernameToken,
    encrypt_password,
    encrypt_created,
    encrypt_nonce,
    build_created_timestamp,
    build_username_token,
    build_security_header_xml,
)

__all__ = [
    "EFaturaCredentials",
    "UsernameToken",
    "encrypt_password",
    "encrypt_created",
    "encrypt_nonce",
    "build_created_timestamp",
    "build_username_token",
    "build_security_header_xml",
]
