from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import base64
import os

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding


@dataclass
class EFaturasCredentials:
    """
    Credenciais do utilizador/subutilizador do Portal das Finanças.

    username: string no formato "<NIF>/<subutilizador>", por ex. "599999993/37"
    password: senha do Portal das Finanças correspondente a esse utilizador
    """
    username: str
    password: str


@dataclass
class UsernameToken:
    """
    Representa os campos do UsernameToken já cifrados e prontos a enviar.
    """
    username: str
    password: str  # Base64(AES_Ks(senha PF))
    nonce: str     # Base64(RSA_KpubSA(Ks))
    created: str   # Base64(AES_Ks(timestamp ISO 8601))

    def to_xml(self) -> str:
        """
        Gera apenas o fragmento <wss:UsernameToken>...</wss:UsernameToken>.
        """
        return (
            "<wss:UsernameToken>"
            f"<wss:Username>{self.username}</wss:Username>"
            f"<wss:Password>{self.password}</wss:Password>"
            f"<wss:Nonce>{self.nonce}</wss:Nonce>"
            f"<wss:Created>{self.created}</wss:Created>"
            "</wss:UsernameToken>"
        )


def _generate_ks() -> bytes:
    """
    Gera a chave simétrica KS de 128 bits (AES).
    """
    return os.urandom(16)


def _aes_encrypt_ecb_pkcs5(plaintext: bytes, key: bytes) -> bytes:
    """
    Cifra com AES-128-ECB e PKCS5/PKCS7 padding, conforme manual da AT.
    """
    if len(key) != 16:
        raise ValueError("KS deve ter exatamente 16 bytes (128 bits)")
    padder = sym_padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    encryptor = cipher.encryptor()
    return encryptor.update(padded) + encryptor.finalize()


def _load_rsa_public_key(public_material_pem: str | bytes) -> rsa.RSAPublicKey:
    """
    Aceita:
      - certificado X.509 em PEM (BEGIN CERTIFICATE)
      - chave pública RSA em PEM (BEGIN PUBLIC KEY / BEGIN RSA PUBLIC KEY)
    e devolve um RSAPublicKey.
    """
    if isinstance(public_material_pem, str):
        data = public_material_pem.encode("ascii")
    else:
        data = public_material_pem

    last_err: Exception | None = None

    # 1) tentar como certificado
    try:
        cert = x509.load_pem_x509_certificate(data)
        pub = cert.public_key()
        if isinstance(pub, rsa.RSAPublicKey):
            return pub
    except Exception as e:  # noqa: BLE001
        last_err = e

    # 2) tentar como chave pública simples
    try:
        pub = serialization.load_pem_public_key(data)
        if isinstance(pub, rsa.RSAPublicKey):
            return pub
        last_err = TypeError("Chave pública não é RSA")
    except Exception as e:  # noqa: BLE001
        last_err = e

    raise ValueError("Não foi possível carregar chave pública RSA da AT") from last_err


def encrypt_password(plain_password: str, ks: bytes) -> str:
    """
    Implementa o campo H.2 - Password:

        Password := Base64( C_AES,ECB,PKCS5Padding_Ks( SenhaPF ) )

    plain_password: senha do Portal das Finanças (UTF-8)
    ks: chave simétrica KS gerada para o pedido (16 bytes)
    """
    ciphertext = _aes_encrypt_ecb_pkcs5(plain_password.encode("utf-8"), ks)
    return base64.b64encode(ciphertext).decode("ascii")


def encrypt_created(timestamp_iso: str, ks: bytes) -> str:
    """
    Implementa o campo H.4 - Created:

        Created := Base64( C_AES,ECB,PKCS5Padding_Ks( Timestamp ) )

    timestamp_iso: data/hora em formato ISO 8601 (UTC), por ex. "2013-01-01T19:20:30.45Z"
    ks: chave simétrica KS (16 bytes)
    """
    ciphertext = _aes_encrypt_ecb_pkcs5(timestamp_iso.encode("utf-8"), ks)
    return base64.b64encode(ciphertext).decode("ascii")


def encrypt_nonce(ks: bytes, public_key_pem: str | bytes) -> str:
    """
    Implementa o campo H.3 - Nonce:

        Nonce := Base64( C_RSA,KpubSA( Ks ) )

    ks: chave simétrica KS (16 bytes)
    public_key_pem: certificado ou chave pública RSA da AT em PEM
    """
    public_key = _load_rsa_public_key(public_key_pem)
    # A documentação refere apenas "algoritmo RSA". A implementação abaixo
    # usa RSA com padding PKCS#1 v1.5, padrão nas integrações AT clássicas.
    ciphertext = public_key.encrypt(ks, asym_padding.PKCS1v15())
    return base64.b64encode(ciphertext).decode("ascii")


def build_created_timestamp(dt: Optional[datetime] = None) -> str:
    """
    Constrói o Timestamp em ISO 8601 UTC, conforme exemplo do manual:

        e.g.: 2013-01-01T19:20:30.45Z

    Por simplicidade, usa milissegundos.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    dt = dt.astimezone(timezone.utc)
    iso = dt.isoformat(timespec="milliseconds")
    return iso.replace("+00:00", "Z")


def build_username_token(
    creds: EFaturasCredentials,
    public_key_pem: str | bytes,
    dt: Optional[datetime] = None,
) -> UsernameToken:
    """
    Cria um UsernameToken completo (Username, Password, Nonce, Created)
    de acordo com o manual de Aspetos Genéricos do e-Fatura.

    - Gera uma KS aleatória de 128 bits;
    - Calcula Password = AES_Ks(senha PF), em Base64;
    - Calcula Created = AES_Ks(timestamp ISO 8601), em Base64;
    - Calcula Nonce = RSA_KpubSA(Ks), em Base64.
    """
    ks = _generate_ks()
    timestamp_iso = build_created_timestamp(dt)

    password_b64 = encrypt_password(creds.password, ks)
    created_b64 = encrypt_created(timestamp_iso, ks)
    nonce_b64 = encrypt_nonce(ks, public_key_pem)

    return UsernameToken(
        username=creds.username,
        password=password_b64,
        nonce=nonce_b64,
        created=created_b64,
    )


def build_security_header_xml(token: UsernameToken) -> str:
    """
    Constrói o fragmento completo do SOAP Header com WS-Security:

        <S:Header>
          <wss:Security xmlns:wss="http://schemas.xmlsoap.org/ws/2002/12/secext">
            <wss:UsernameToken>...</wss:UsernameToken>
          </wss:Security>
        </S:Header>
    """
    return (
        "<S:Header>"
        '<wss:Security xmlns:wss="http://schemas.xmlsoap.org/ws/2002/12/secext">'
        f"{token.to_xml()}"
        "</wss:Security>"
        "</S:Header>"
    )
