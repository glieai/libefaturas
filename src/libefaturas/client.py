"""Client helpers for interacting with the AT e-fatura webservices."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import xml.etree.ElementTree as ET

import requests

from .config import ENDPOINTS, Environment
from .security import (
    EFaturasCredentials,
    build_security_header_xml,
    build_username_token,
)


__all__ = ["EFaturasClient", "test_connection"]


class EFaturasClient:
    def __init__(
        self,
        *,
        username: str,
        password: str,
        public_key_path: str,
        client_cert_path: str,
        client_key_path: Optional[str] = None,
        ca_cert_path: Optional[str] = None,
        environment: str = "test",
        timeout: int = 30,
    ) -> None:
        self.username = username
        self.password = password
        self.public_key_path = public_key_path
        self.client_cert_path = client_cert_path
        self.client_key_path = client_key_path
        self.ca_cert_path = ca_cert_path
        self.timeout = timeout
        self.environment = Environment(environment.lower())

        creds = EFaturasCredentials(username=username, password=password)
        public_pem = Path(public_key_path).read_bytes()
        token = build_username_token(creds, public_pem)
        self._security_header_xml = build_security_header_xml(token)

    def _resolve_endpoint(self, service: str, endpoint: Optional[str]) -> str:
        service_norm = (service or "faturas").lower()
        if endpoint:
            return endpoint
        endpoints = ENDPOINTS[self.environment]
        if service_norm == "series":
            return endpoints.series
        return endpoints.faturas

    def post(
        self,
        *,
        service: str,
        body_xml: str,
        endpoint: Optional[str] = None,
    ) -> requests.Response:
        envelope = self.build_envelope_xml(body_xml)

        if self.client_key_path:
            cert = (self.client_cert_path, self.client_key_path)
        else:
            cert = self.client_cert_path

        verify = self.ca_cert_path if self.ca_cert_path else True

        effective_endpoint = self._resolve_endpoint(service, endpoint)

        response = requests.post(
            effective_endpoint,
            data=envelope.encode("utf-8"),
            headers={"Content-Type": "text/xml; charset=utf-8"},
            cert=cert,
            verify=verify,
            timeout=self.timeout,
        )
        return response

    def build_envelope_xml(self, body_xml: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">'
            f"{self._security_header_xml}"
            f"{body_xml}"
            "</S:Envelope>"
        )


def test_connection(
    *,
    username: str,
    password: str,
    public_key_path: str,
    client_cert_path: str,
    endpoint: Optional[str] = None,
    environment: str = "test",
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
        client = EFaturasClient(
            username=username,
            password=password,
            public_key_path=public_key_path,
            client_cert_path=client_cert_path,
            client_key_path=client_key_path,
            ca_cert_path=ca_cert_path,
            environment=environment,
            timeout=timeout,
        )
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

    try:
        response = client.post(
            service=service_norm,
            body_xml=body_xml,
            endpoint=endpoint,
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
