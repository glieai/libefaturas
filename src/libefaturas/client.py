"""Client helpers for interacting with the AT e-fatura webservices."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import xml.etree.ElementTree as ET

import requests

from .security import (
    EFaturaCredentials,
    build_security_header_xml,
    build_username_token,
)


__all__ = ["test_connection"]


def test_connection(
    *,
    username: str,
    password: str,
    public_key_path: str,
    endpoint: str,
    client_cert_path: str,
    client_key_path: Optional[str] = None,
    ca_cert_path: Optional[str] = None,
    timeout: int = 30,
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
        creds = EFaturaCredentials(username=username, password=password)
        public_pem = Path(public_key_path).read_bytes()
        token = build_username_token(creds, public_pem)
        header_xml = build_security_header_xml(token)
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

    envelope = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">'
        f"{header_xml}"
        f"{body_xml}"
        "</S:Envelope>"
    )

    if client_key_path:
        cert = (client_cert_path, client_key_path)
    else:
        cert = client_cert_path

    verify = ca_cert_path if ca_cert_path else True

    try:
        response = requests.post(
            endpoint,
            data=envelope.encode("utf-8"),
            headers={"Content-Type": "text/xml; charset=utf-8"},
            cert=cert,
            verify=verify,
            timeout=timeout,
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
