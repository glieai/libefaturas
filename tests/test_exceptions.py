"""Tests for custom exceptions."""

import pytest

from libefaturas.exceptions import (
    EFaturasAuthError,
    EFaturasConnectionError,
    EFaturasError,
    EFaturasKeyError,
    EFaturasRetryError,
    EFaturasSOAPError,
    EFaturasValidationError,
)


class TestEFaturasError:
    """Tests for base exception."""

    def test_basic_error(self):
        """Test basic error creation."""
        exc = EFaturasError("Test error")
        assert str(exc) == "Test error"
        assert exc.message == "Test error"
        assert exc.details is None

    def test_error_with_details(self):
        """Test error with details."""
        exc = EFaturasError("Test error", details={"key": "value"})
        assert "key" in str(exc)
        assert exc.details == {"key": "value"}

    def test_inheritance(self):
        """Test that all exceptions inherit from EFaturasError."""
        assert issubclass(EFaturasConnectionError, EFaturasError)
        assert issubclass(EFaturasAuthError, EFaturasError)
        assert issubclass(EFaturasValidationError, EFaturasError)
        assert issubclass(EFaturasSOAPError, EFaturasError)
        assert issubclass(EFaturasRetryError, EFaturasError)
        assert issubclass(EFaturasKeyError, EFaturasError)


class TestEFaturasConnectionError:
    """Tests for connection errors."""

    def test_basic(self):
        """Test basic connection error."""
        exc = EFaturasConnectionError("Connection failed")
        assert exc.endpoint is None
        assert exc.original_error is None

    def test_with_endpoint(self):
        """Test connection error with endpoint."""
        exc = EFaturasConnectionError(
            "Connection failed",
            endpoint="https://example.com/api",
        )
        assert exc.endpoint == "https://example.com/api"

    def test_with_original_error(self):
        """Test connection error with original exception."""
        original = TimeoutError("Timeout")
        exc = EFaturasConnectionError(
            "Connection failed",
            original_error=original,
        )
        assert exc.original_error == original


class TestEFaturasAuthError:
    """Tests for authentication errors."""

    def test_basic(self):
        """Test basic auth error."""
        exc = EFaturasAuthError("Authentication failed")
        assert exc.fault_code is None
        assert exc.fault_string is None

    def test_with_fault_info(self):
        """Test auth error with SOAP fault info."""
        exc = EFaturasAuthError(
            "Authentication failed",
            fault_code="wsse:FailedAuthentication",
            fault_string="The security token could not be authenticated",
        )
        assert exc.fault_code == "wsse:FailedAuthentication"
        assert exc.fault_string == "The security token could not be authenticated"


class TestEFaturasValidationError:
    """Tests for validation errors."""

    def test_basic(self):
        """Test basic validation error."""
        exc = EFaturasValidationError("Invalid input")
        assert exc.field is None
        assert exc.value is None

    def test_with_field_info(self):
        """Test validation error with field info."""
        exc = EFaturasValidationError(
            "Invalid tax rate",
            field="tax_rate",
            value=-5,
        )
        assert exc.field == "tax_rate"
        assert exc.value == -5


class TestEFaturasSOAPError:
    """Tests for SOAP errors."""

    def test_basic(self):
        """Test basic SOAP error."""
        exc = EFaturasSOAPError("SOAP fault")
        assert exc.code is None
        assert exc.raw_response is None

    def test_with_details(self):
        """Test SOAP error with details."""
        exc = EFaturasSOAPError(
            "Document rejected",
            code=1001,
            fault_code="env:Server",
            fault_string="Internal error",
            raw_response="<soap:Fault>...</soap:Fault>",
        )
        assert exc.code == 1001
        assert exc.fault_code == "env:Server"
        assert exc.raw_response == "<soap:Fault>...</soap:Fault>"


class TestEFaturasRetryError:
    """Tests for retry errors."""

    def test_basic(self):
        """Test basic retry error."""
        exc = EFaturasRetryError("All retries failed", attempts=3)
        assert exc.attempts == 3
        assert exc.last_error is None

    def test_with_last_error(self):
        """Test retry error with last exception."""
        last = TimeoutError("Last timeout")
        exc = EFaturasRetryError(
            "All retries failed",
            attempts=5,
            last_error=last,
        )
        assert exc.attempts == 5
        assert exc.last_error == last


class TestEFaturasKeyError:
    """Tests for key errors."""

    def test_basic(self):
        """Test basic key error."""
        exc = EFaturasKeyError("Invalid key")
        assert exc.key_path is None
        assert exc.key_type is None

    def test_with_key_info(self):
        """Test key error with key info."""
        exc = EFaturasKeyError(
            "Key too large for SAF-T",
            key_path="/path/to/key.pem",
            key_type="RSA-2048",
        )
        assert exc.key_path == "/path/to/key.pem"
        assert exc.key_type == "RSA-2048"


class TestExceptionCatching:
    """Tests for exception hierarchy in try/except."""

    def test_catch_all_with_base(self):
        """Test catching all library exceptions with base class."""
        exceptions = [
            EFaturasConnectionError("test"),
            EFaturasAuthError("test"),
            EFaturasValidationError("test"),
            EFaturasSOAPError("test"),
            EFaturasRetryError("test", attempts=1),
            EFaturasKeyError("test"),
        ]
        for exc in exceptions:
            try:
                raise exc
            except EFaturasError as e:
                assert e is exc
            except Exception:
                pytest.fail(f"{type(exc).__name__} not caught by EFaturasError")

    def test_catch_specific(self):
        """Test catching specific exception types."""
        try:
            raise EFaturasConnectionError("test")
        except EFaturasSOAPError:
            pytest.fail("Should not catch as SOAPError")
        except EFaturasConnectionError:
            pass  # Expected

    def test_exception_is_exception(self):
        """Test that our exceptions are standard Python exceptions."""
        exc = EFaturasError("test")
        assert isinstance(exc, Exception)
