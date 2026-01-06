"""Retry utilities for transient failures.

This module provides configurable retry logic with exponential backoff
for handling transient network issues when communicating with AT services.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Set, Type, TypeVar

import requests

from .exceptions import EFaturasConnectionError, EFaturasRetryError

_logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of attempts (including initial). Default: 3
        base_delay: Initial delay in seconds between retries. Default: 1.0
        max_delay: Maximum delay in seconds. Default: 30.0
        exponential_base: Multiplier for exponential backoff. Default: 2.0
        jitter: Add random jitter (0-1) to delay to avoid thundering herd. Default: 0.1
        retryable_exceptions: Set of exception types to retry on.
        retryable_status_codes: HTTP status codes that should trigger a retry.
    """

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: float = 0.1
    retryable_exceptions: Set[Type[Exception]] = field(
        default_factory=lambda: {
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
            ConnectionResetError,
            ConnectionRefusedError,
            ConnectionAbortedError,
            TimeoutError,
            OSError,  # Includes network-level errors
        }
    )
    retryable_status_codes: Set[int] = field(
        default_factory=lambda: {
            408,  # Request Timeout
            429,  # Too Many Requests
            500,  # Internal Server Error
            502,  # Bad Gateway
            503,  # Service Unavailable
            504,  # Gateway Timeout
        }
    )


# Default configuration - can be overridden per-client
DEFAULT_RETRY_CONFIG = RetryConfig()


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for a given attempt number using exponential backoff.

    Args:
        attempt: The attempt number (0-indexed)
        config: Retry configuration

    Returns:
        Delay in seconds with optional jitter applied
    """
    delay = config.base_delay * (config.exponential_base ** attempt)
    delay = min(delay, config.max_delay)

    if config.jitter > 0:
        jitter_amount = delay * config.jitter * random.random()
        delay += jitter_amount

    return delay


def is_retryable_exception(exc: Exception, config: RetryConfig) -> bool:
    """Check if an exception is retryable based on configuration.

    Args:
        exc: The exception to check
        config: Retry configuration

    Returns:
        True if the exception should trigger a retry
    """
    return any(isinstance(exc, exc_type) for exc_type in config.retryable_exceptions)


def is_retryable_response(response: requests.Response, config: RetryConfig) -> bool:
    """Check if an HTTP response should trigger a retry.

    Args:
        response: The HTTP response to check
        config: Retry configuration

    Returns:
        True if the response status code should trigger a retry
    """
    return response.status_code in config.retryable_status_codes


def retry_request(
    func: Callable[[], requests.Response],
    config: Optional[RetryConfig] = None,
    endpoint: Optional[str] = None,
) -> requests.Response:
    """Execute a request function with retry logic.

    Args:
        func: A callable that returns a requests.Response
        config: Retry configuration (uses DEFAULT_RETRY_CONFIG if not provided)
        endpoint: Optional endpoint URL for error messages

    Returns:
        The successful response

    Raises:
        EFaturasRetryError: If all retry attempts are exhausted
        EFaturasConnectionError: If a non-retryable connection error occurs
    """
    if config is None:
        config = DEFAULT_RETRY_CONFIG

    last_error: Optional[Exception] = None

    for attempt in range(config.max_attempts):
        try:
            response = func()

            # Check if we should retry based on status code
            if is_retryable_response(response, config):
                if attempt < config.max_attempts - 1:
                    delay = calculate_delay(attempt, config)
                    _logger.warning(
                        "Retryable status %d from %s, retrying in %.2fs (attempt %d/%d)",
                        response.status_code,
                        endpoint or "AT",
                        delay,
                        attempt + 1,
                        config.max_attempts,
                    )
                    time.sleep(delay)
                    continue
                else:
                    # Last attempt, return the response anyway
                    _logger.warning(
                        "Retryable status %d from %s, no more retries",
                        response.status_code,
                        endpoint or "AT",
                    )

            return response

        except Exception as exc:  # noqa: BLE001
            last_error = exc

            if not is_retryable_exception(exc, config):
                raise EFaturasConnectionError(
                    f"Erro de ligação não recuperável: {exc}",
                    endpoint=endpoint,
                    original_error=exc,
                ) from exc

            if attempt < config.max_attempts - 1:
                delay = calculate_delay(attempt, config)
                _logger.warning(
                    "Retryable error from %s: %s, retrying in %.2fs (attempt %d/%d)",
                    endpoint or "AT",
                    exc,
                    delay,
                    attempt + 1,
                    config.max_attempts,
                )
                time.sleep(delay)
            else:
                _logger.error(
                    "All %d retry attempts exhausted for %s: %s",
                    config.max_attempts,
                    endpoint or "AT",
                    exc,
                )

    raise EFaturasRetryError(
        f"Todas as {config.max_attempts} tentativas falharam",
        attempts=config.max_attempts,
        last_error=last_error,
    )
