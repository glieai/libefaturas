"""Command-line interface for libefaturas."""

from __future__ import annotations

import argparse
import getpass
import sys

from .client import test_connection

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

    result = test_connection(
        username=args.username,
        password=password,
        public_key_path=args.public_key,
        client_cert_path=args.client_cert,
        client_key_path=args.client_key,
        ca_cert_path=args.ca_cert,
        environment=args.env,
        endpoint=args.endpoint,
        service=args.service,
    )

    print("[1] UsernameToken:", "OK" if result["username_token_ok"] else "FALHOU")
    print("[2] TLS/HTTP:", "OK" if result["tls_ok"] else "FALHOU")

    if result["http_status"] is not None:
        print(f"[3] HTTP status: {result['http_status']}")

    if result["soap_fault_code"] or result["soap_fault_string"]:
        print("[4] SOAP Fault detectado:")
        if result["soap_fault_code"]:
            print(f"    faultcode: {result['soap_fault_code']}")
        if result["soap_fault_string"]:
            print(f"    faultstring: {result['soap_fault_string']}")
    else:
        print("[4] SOAP Fault: nenhum Fault detetado (para o body enviado)")

    if result["error"]:
        print(f"[ERRO] {result['error']}")

    if result["raw_response_snippet"]:
        print("\n[RAW RESPONSE - primeiros 1000 bytes]")
        print(result["raw_response_snippet"])

    if result["username_token_ok"] and result["tls_ok"]:
        sys.exit(0)
    sys.exit(1)

