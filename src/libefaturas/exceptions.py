"""Custom exceptions for libefaturas.

This module defines a hierarchy of exceptions that provide clear error
categorization for different failure modes when interacting with AT services.
"""

from __future__ import annotations

from typing import Any, Optional


class EFaturasError(Exception):
    """Base exception for all libefaturas errors.

    All exceptions raised by libefaturas inherit from this class,
    allowing callers to catch all library errors with a single except clause.
    """

    def __init__(self, message: str, *, details: Optional[Any] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class EFaturasConnectionError(EFaturasError):
    """Raised when there's a network/TLS connection failure.

    This includes:
    - DNS resolution failures
    - TLS handshake failures
    - Connection timeouts
    - Connection resets
    """

    def __init__(
        self,
        message: str,
        *,
        endpoint: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        super().__init__(message, details={"endpoint": endpoint, "original_error": str(original_error)})
        self.endpoint = endpoint
        self.original_error = original_error


class EFaturasAuthError(EFaturasError):
    """Raised when authentication with AT services fails.

    This includes:
    - Invalid credentials
    - Expired certificates
    - Invalid UsernameToken
    - Permission denied
    """

    def __init__(
        self,
        message: str,
        *,
        fault_code: Optional[str] = None,
        fault_string: Optional[str] = None,
    ) -> None:
        super().__init__(message, details={"fault_code": fault_code, "fault_string": fault_string})
        self.fault_code = fault_code
        self.fault_string = fault_string


class EFaturasValidationError(EFaturasError):
    """Raised when input validation fails before sending to AT.

    This includes:
    - Missing required fields
    - Invalid field formats
    - Invalid document types
    - Invalid tax codes
    """

    def __init__(
        self,
        message: str,
        *,
        field: Optional[str] = None,
        value: Optional[Any] = None,
    ) -> None:
        super().__init__(message, details={"field": field, "value": value})
        self.field = field
        self.value = value


class EFaturasSOAPError(EFaturasError):
    """Raised when AT returns a SOAP fault or error response.

    This includes:
    - Business logic errors from AT
    - Invalid document data
    - Series conflicts
    """

    def __init__(
        self,
        message: str,
        *,
        code: Optional[int] = None,
        fault_code: Optional[str] = None,
        fault_string: Optional[str] = None,
        raw_response: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            details={
                "code": code,
                "fault_code": fault_code,
                "fault_string": fault_string,
            },
        )
        self.code = code
        self.fault_code = fault_code
        self.fault_string = fault_string
        self.raw_response = raw_response


class EFaturasRetryError(EFaturasError):
    """Raised when all retry attempts have been exhausted.

    Contains information about the number of attempts made and the last error.
    """

    def __init__(
        self,
        message: str,
        *,
        attempts: int,
        last_error: Optional[Exception] = None,
    ) -> None:
        super().__init__(message, details={"attempts": attempts, "last_error": str(last_error)})
        self.attempts = attempts
        self.last_error = last_error


class EFaturasKeyError(EFaturasError):
    """Raised when there's an issue with cryptographic keys.

    This includes:
    - Invalid key format
    - Wrong key size (e.g., not 1024-bit for SAF-T)
    - Password protected key without password
    - Key file not found
    """

    def __init__(
        self,
        message: str,
        *,
        key_path: Optional[str] = None,
        key_type: Optional[str] = None,
    ) -> None:
        super().__init__(message, details={"key_path": key_path, "key_type": key_type})
        self.key_path = key_path
        self.key_type = key_type
