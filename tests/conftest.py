"""
Pytest fixtures for libefaturas tests.
"""
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization


@pytest.fixture
def rsa_key_pair():
    """Generate a test RSA key pair (1024-bit for SAF-T compatibility)."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=1024,  # AT requires 1024-bit for SAF-T
    )
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return {
        "private_key": private_key,
        "public_key": public_key,
        "private_pem": private_pem,
        "public_pem": public_pem,
    }


@pytest.fixture
def password_protected_key():
    """Generate a password-protected test RSA key pair."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=1024,
    )

    password = b"test_password_123"

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(password),
    )

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return {
        "private_pem": private_pem,
        "public_pem": public_pem,
        "password": password,
    }


@pytest.fixture
def sample_invoice_data():
    """Sample invoice data for hash generation tests."""
    return {
        "invoice_date": "2025-01-15",
        "system_entry_date": "2025-01-15T10:30:00",
        "invoice_no": "FT FT2025/000001",
        "gross_total": "123.00",
        "previous_hash": "",  # First document
    }


@pytest.fixture
def sample_credentials():
    """Sample e-Fatura credentials for testing."""
    from libefaturas.security import EFaturasCredentials
    return EFaturasCredentials(
        username="599999993/37",
        password="test_password",
    )
