"""
CLI para teste de ligação ao webservice da AT.

Permite verificar rapidamente:
- se a chave pública da AT é válida (para gerar Nonce)
- se as credenciais permitem gerar Password/Created
- se o endpoint HTTPS aceita o certificado cliente (handshake TLS)
"""

import argparse
import getpass
import sys

from . import test_connection


def main() -> None:
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
        "--endpoint",
        required=True,
        help=(
            "URL do endpoint SOAP da AT "
            "(ex.: https://servicos.portaldasfinancas.gov.pt:400/fews/faturas)."
        ),
    )
    parser.add_argument(
        "--service",
        choices=["faturas", "series"],
        default="faturas",
        help="Tipo de serviço a testar: 'faturas' ou 'series'.",
    )

    args = parser.parse_args()

    password = args.password or getpass.getpass("Senha do Portal das Finanças: ")

    result = test_connection(
        username=args.username,
        password=password,
        public_key_path=args.public_key,
        endpoint=args.endpoint,
        client_cert_path=args.client_cert,
        client_key_path=args.client_key,
        ca_cert_path=args.ca_cert,
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

    # exit code simples: 0 se UsernameToken + TLS OK, 1 caso contrário
    if result["username_token_ok"] and result["tls_ok"]:
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
