"""
Tests for libefaturas.security module.

Tests cover:
- AES encryption for UsernameToken
- RSA encryption for Nonce
- SAF-T hash generation
- UsernameToken building
"""
import base64
import pytest
from datetime import datetime, timezone

from libefaturas.security import (
    EFaturasCredentials,
    UsernameToken,
    build_username_token,
    build_created_timestamp,
    build_security_header_xml,
    encrypt_password,
    encrypt_created,
    encrypt_nonce,
    gerar_hash_fatura,
    _aes_encrypt_ecb_pkcs5,
    _generate_ks,
)


class TestAESEncryption:
    """Tests for AES-128-ECB encryption functions."""

    def test_generate_ks_length(self):
        """KS should be exactly 16 bytes (128 bits)."""
        ks = _generate_ks()
        assert len(ks) == 16

    def test_generate_ks_randomness(self):
        """Each call should generate different keys."""
        keys = [_generate_ks() for _ in range(10)]
        # All keys should be unique
        assert len(set(keys)) == 10

    def test_aes_encrypt_basic(self):
        """Basic AES encryption should work."""
        ks = b"0123456789abcdef"  # 16 bytes
        plaintext = b"Hello World!"
        ciphertext = _aes_encrypt_ecb_pkcs5(plaintext, ks)
        assert ciphertext != plaintext
        assert len(ciphertext) % 16 == 0  # Block aligned with padding

    def test_aes_encrypt_invalid_key_length(self):
        """AES encryption should reject invalid key lengths."""
        with pytest.raises(ValueError, match="16 bytes"):
            _aes_encrypt_ecb_pkcs5(b"test", b"short_key")

    def test_encrypt_password(self):
        """Password encryption should return base64 string."""
        ks = b"0123456789abcdef"
        result = encrypt_password("my_secret_password", ks)
        # Should be valid base64
        decoded = base64.b64decode(result)
        assert len(decoded) > 0
        assert len(decoded) % 16 == 0

    def test_encrypt_created(self):
        """Created timestamp encryption should return base64 string."""
        ks = b"0123456789abcdef"
        timestamp = "2025-01-15T10:30:00.000Z"
        result = encrypt_created(timestamp, ks)
        decoded = base64.b64decode(result)
        assert len(decoded) > 0
        assert len(decoded) % 16 == 0


class TestRSAEncryption:
    """Tests for RSA encryption functions."""

    def test_encrypt_nonce(self, rsa_key_pair):
        """Nonce encryption should work with valid public key."""
        ks = _generate_ks()
        result = encrypt_nonce(ks, rsa_key_pair["public_pem"])
        # Should be valid base64
        decoded = base64.b64decode(result)
        # RSA 1024-bit produces 128-byte ciphertext
        assert len(decoded) == 128

    def test_encrypt_nonce_with_string_key(self, rsa_key_pair):
        """Nonce encryption should accept string PEM."""
        ks = _generate_ks()
        public_pem_str = rsa_key_pair["public_pem"].decode("ascii")
        result = encrypt_nonce(ks, public_pem_str)
        decoded = base64.b64decode(result)
        assert len(decoded) == 128


class TestUsernameToken:
    """Tests for UsernameToken building."""

    def test_build_created_timestamp(self):
        """Timestamp should be in ISO 8601 format with Z suffix."""
        dt = datetime(2025, 1, 15, 10, 30, 0, 123000, tzinfo=timezone.utc)
        result = build_created_timestamp(dt)
        assert result == "2025-01-15T10:30:00.123Z"

    def test_build_created_timestamp_no_arg(self):
        """Timestamp without argument should use current time."""
        result = build_created_timestamp()
        assert result.endswith("Z")
        assert "T" in result

    def test_build_username_token(self, rsa_key_pair, sample_credentials):
        """Should build complete UsernameToken."""
        token = build_username_token(
            sample_credentials,
            rsa_key_pair["public_pem"],
        )
        assert isinstance(token, UsernameToken)
        assert token.username == "599999993/37"
        # Password, Nonce, Created should all be base64
        base64.b64decode(token.password)
        base64.b64decode(token.nonce)
        base64.b64decode(token.created)

    def test_username_token_to_xml(self, rsa_key_pair, sample_credentials):
        """Token should serialize to valid XML fragment."""
        token = build_username_token(
            sample_credentials,
            rsa_key_pair["public_pem"],
        )
        xml = token.to_xml()
        assert "<wss:UsernameToken>" in xml
        assert "</wss:UsernameToken>" in xml
        assert "<wss:Username>599999993/37</wss:Username>" in xml
        assert "<wss:Password>" in xml
        assert "<wss:Nonce>" in xml
        assert "<wss:Created>" in xml

    def test_build_security_header_xml(self, rsa_key_pair, sample_credentials):
        """Should build complete SOAP Security header."""
        token = build_username_token(
            sample_credentials,
            rsa_key_pair["public_pem"],
        )
        xml = build_security_header_xml(token)
        assert "<S:Header>" in xml
        assert "</S:Header>" in xml
        assert '<wss:Security xmlns:wss=' in xml


class TestHashGeneration:
    """Tests for SAF-T hash generation (gerar_hash_fatura)."""

    def test_hash_generation_basic(self, rsa_key_pair, sample_invoice_data):
        """Basic hash generation should work."""
        result = gerar_hash_fatura(
            invoice_date=sample_invoice_data["invoice_date"],
            system_entry_date=sample_invoice_data["system_entry_date"],
            invoice_no=sample_invoice_data["invoice_no"],
            gross_total=sample_invoice_data["gross_total"],
            previous_hash=sample_invoice_data["previous_hash"],
            private_key_pem=rsa_key_pair["private_pem"],
        )
        # Result should be base64 encoded
        decoded = base64.b64decode(result)
        # RSA 1024-bit signature is 128 bytes
        assert len(decoded) == 128

    def test_hash_deterministic(self, rsa_key_pair, sample_invoice_data):
        """Same inputs should produce same hash."""
        hash1 = gerar_hash_fatura(
            invoice_date=sample_invoice_data["invoice_date"],
            system_entry_date=sample_invoice_data["system_entry_date"],
            invoice_no=sample_invoice_data["invoice_no"],
            gross_total=sample_invoice_data["gross_total"],
            previous_hash=sample_invoice_data["previous_hash"],
            private_key_pem=rsa_key_pair["private_pem"],
        )
        hash2 = gerar_hash_fatura(
            invoice_date=sample_invoice_data["invoice_date"],
            system_entry_date=sample_invoice_data["system_entry_date"],
            invoice_no=sample_invoice_data["invoice_no"],
            gross_total=sample_invoice_data["gross_total"],
            previous_hash=sample_invoice_data["previous_hash"],
            private_key_pem=rsa_key_pair["private_pem"],
        )
        assert hash1 == hash2

    def test_hash_with_previous(self, rsa_key_pair, sample_invoice_data):
        """Hash with previous_hash should be different from first document."""
        hash_first = gerar_hash_fatura(
            invoice_date=sample_invoice_data["invoice_date"],
            system_entry_date=sample_invoice_data["system_entry_date"],
            invoice_no=sample_invoice_data["invoice_no"],
            gross_total=sample_invoice_data["gross_total"],
            previous_hash="",  # First doc
            private_key_pem=rsa_key_pair["private_pem"],
        )
        hash_second = gerar_hash_fatura(
            invoice_date=sample_invoice_data["invoice_date"],
            system_entry_date=sample_invoice_data["system_entry_date"],
            invoice_no="FT FT2025/000002",
            gross_total=sample_invoice_data["gross_total"],
            previous_hash=hash_first,  # Chain from first
            private_key_pem=rsa_key_pair["private_pem"],
        )
        assert hash_first != hash_second

    def test_hash_with_password_protected_key(self, password_protected_key, sample_invoice_data):
        """Hash generation should work with password-protected keys."""
        result = gerar_hash_fatura(
            invoice_date=sample_invoice_data["invoice_date"],
            system_entry_date=sample_invoice_data["system_entry_date"],
            invoice_no=sample_invoice_data["invoice_no"],
            gross_total=sample_invoice_data["gross_total"],
            previous_hash="",
            private_key_pem=password_protected_key["private_pem"],
            password=password_protected_key["password"],
        )
        decoded = base64.b64decode(result)
        assert len(decoded) == 128

    def test_hash_message_format(self, rsa_key_pair):
        """Hash message should follow AT format: date;datetime;invoiceno;total;prevhash"""
        # This test verifies the message format by checking signature verification
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives import hashes

        invoice_date = "2025-01-15"
        system_entry_date = "2025-01-15T10:30:00"
        invoice_no = "FT FT2025/000001"
        gross_total = "123.00"
        previous_hash = ""

        result = gerar_hash_fatura(
            invoice_date=invoice_date,
            system_entry_date=system_entry_date,
            invoice_no=invoice_no,
            gross_total=gross_total,
            previous_hash=previous_hash,
            private_key_pem=rsa_key_pair["private_pem"],
        )

        # Verify signature
        signature = base64.b64decode(result)
        expected_message = f"{invoice_date};{system_entry_date};{invoice_no};{gross_total};{previous_hash}"

        # This will raise if signature is invalid
        rsa_key_pair["public_key"].verify(
            signature,
            expected_message.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA1(),
        )


class TestEFaturasCredentials:
    """Tests for EFaturasCredentials dataclass."""

    def test_credentials_creation(self):
        """Should create credentials with username and password."""
        creds = EFaturasCredentials(
            username="599999993/37",
            password="secret123",
        )
        assert creds.username == "599999993/37"
        assert creds.password == "secret123"

    def test_credentials_with_special_chars(self):
        """Should handle special characters in password."""
        creds = EFaturasCredentials(
            username="123456789/1",
            password="p@$$w0rd!<>&\"'",
        )
        assert creds.password == "p@$$w0rd!<>&\"'"
