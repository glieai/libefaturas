"""Command-line interface for libefaturas."""

from __future__ import annotations

import argparse
import getpass
import sys

from .client import EFaturasClient

__all__ = ["main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Teste de ligação ao webservice AT.")
    parser.add_argument("--username", required=True, help="<NIF>/<subutilizador>")
    parser.add_argument(
        "--password",
        help="Senha do Portal das Finanças (se omitida, é pedida interativamente).",
    )
    parser.add_argument(
        "--public-key",
        required=True,
        help="Caminho para a chave pública/certificado da AT em PEM.",
    )
    parser.add_argument(
        "--client-cert",
        required=True,
        help=(
            "Caminho para o certificado cliente (PEM). "
            "Se contiver também a chave privada, não uses --client-key."
        ),
    )
    parser.add_argument(
        "--client-key",
        help=(
            "Caminho para a chave privada do certificado cliente (PEM), "
            "caso esteja separada do ficheiro --client-cert."
        ),
    )
    parser.add_argument(
        "--ca-cert",
        help=(
            "Caminho para bundle de CAs (opcional). "
            "Se omitido, usa o default do sistema."
        ),
    )
    parser.add_argument(
        "--env",
        choices=["test", "prod"],
        default="test",
        help="Ambiente da AT: 'test' ou 'prod' (por omissão, 'test').",
    )
    parser.add_argument(
        "--endpoint",
        help=(
            "Override manual do endpoint SOAP da AT. "
            "Se omitido, é usado o endpoint padrão para o ambiente/serviço."
        ),
    )
    parser.add_argument(
        "--service",
        choices=["faturas", "series"],
        default="faturas",
        help="Tipo de serviço a testar: 'faturas' ou 'series'.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    password = args.password or getpass.getpass("Senha do Portal das Finanças: ")

    client = EFaturasClient(
        username=args.username,
        password=password,
        public_key_path=args.public_key,
        client_cert_path=args.client_cert,
        client_key_path=args.client_key,
        ca_cert_path=args.ca_cert,
        environment=args.env,
        faturas_endpoint=args.endpoint if args.service == "faturas" else None,
        series_endpoint=args.endpoint if args.service == "series" else None,
    )

    result = client.test_connection(service=args.service)
    details = result.data or {}

    print("[1] UsernameToken:", "OK" if details.get("username_token_ok") else "FALHOU")
    print("[2] TLS/HTTP:", "OK" if details.get("tls_ok") else "FALHOU")

    if details.get("http_status") is not None:
        print(f"[3] HTTP status: {details['http_status']}")

    if details.get("soap_fault_code") or details.get("soap_fault_string"):
        print("[4] SOAP Fault detectado:")
        if details.get("soap_fault_code"):
            print(f"    faultcode: {details['soap_fault_code']}")
        if details.get("soap_fault_string"):
            print(f"    faultstring: {details['soap_fault_string']}")
    else:
        print("[4] SOAP Fault: nenhum Fault detetado (para o body enviado)")

    if details.get("error"):
        print(f"[ERRO] {details['error']}")
    if result.message:
        print(f"[INFO] {result.message}")

    if details.get("raw_response_snippet"):
        print("\n[RAW RESPONSE - primeiros 1000 bytes]")
        print(details["raw_response_snippet"])

    if result.ok:
        sys.exit(0)
    sys.exit(1)
