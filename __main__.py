"""
CLI para teste de ligação ao webservice da AT.

Permite verificar rapidamente:
- se a chave pública da AT é válida (para gerar Nonce)
- se as credenciais permitem gerar Password/Created
- se o endpoint HTTPS aceita o certificado cliente (handshake TLS)
"""

from pathlib import Path
import argparse
import getpass

import requests

from . import (
    EFaturaCredentials,
    build_username_token,
    build_security_header_xml,
)


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

    args = parser.parse_args()

    password = args.password or getpass.getpass("Senha do Portal das Finanças: ")

    creds = EFaturaCredentials(username=args.username, password=password)
    public_pem = Path(args.public_key).read_bytes()

    # 1) gerar UsernameToken (valida já toda a parte criptográfica)
    token = build_username_token(creds, public_pem)
    header_xml = build_security_header_xml(token)

    # 2) envelope SOAP mínimo (body dummy; objetivo é só handshake + auth de transporte)
    envelope = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">'
        f"{header_xml}"
        "<S:Body>"
        '<ef:ConnectionTest xmlns:ef="urn:efatura-auth-test">ok</ef:ConnectionTest>'
        "</S:Body>"
        "</S:Envelope>"
    )

    # 3) certificado cliente
    if args.client_key:
        cert = (args.client_cert, args.client_key)
    else:
        cert = args.client_cert

    verify = args.ca_cert if args.ca_cert else True

    response = requests.post(
        args.endpoint,
        data=envelope.encode("utf-8"),
        headers={"Content-Type": "text/xml; charset=utf-8"},
        cert=cert,
        verify=verify,
        timeout=30,
    )

    print(f"HTTP status: {response.status_code}")
    print("Response headers:")
    for k, v in response.headers.items():
        print(f"  {k}: {v}")

    print("\nPrimeiros 1000 bytes da resposta:")
    print(response.text[:1000])


if __name__ == "__main__":
    main()
