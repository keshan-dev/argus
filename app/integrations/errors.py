"""Typed exceptions for external integration clients and HTTP operations.

Maps upstream HTTP status codes and transport failures to structured error types
defined in the frozen contracts (P1-002, P2-001, FR-033).
"""

from typing import Any

from app.schemas.errors import ToolErrorType, ToolFailure


class IntegrationError(Exception):
    """Base exception for all external integration failures."""

    error_type: ToolErrorType = "UPSTREAM_ERROR"

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
        **extra: Any,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        self.extra = extra

    def to_tool_failure(self, tool_id: str) -> ToolFailure:
        """Convert this integration error into a frozen ToolFailure schema contract."""
        return ToolFailure(
            tool_id=tool_id,
            error_type=self.error_type,
            detail=self.message,
        )


class IntegrationTimeoutError(IntegrationError):
    """Network connection or read timeout during upstream request (maps to TIMEOUT)."""

    error_type: ToolErrorType = "TIMEOUT"


class AuthError(IntegrationError):
    """Authentication or authorization failure e.g. 401/403 (maps to AUTH_FAILED)."""

    error_type: ToolErrorType = "AUTH_FAILED"


class RateLimitError(IntegrationError):
    """Upstream rate limit or quota exceeded e.g. 429 or 403 (maps to RATE_LIMITED)."""

    error_type: ToolErrorType = "RATE_LIMITED"

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
        retry_after: float | None = None,
        **extra: Any,
    ) -> None:
        super().__init__(message, status_code, response_body, **extra)
        self.retry_after = retry_after


class NotFoundError(IntegrationError):
    """Requested upstream resource does not exist e.g. 404 (maps to NOT_FOUND)."""

    error_type: ToolErrorType = "NOT_FOUND"


class UpstreamError(IntegrationError):
    """Server-side failure or connection disruption e.g. 5xx (maps to UPSTREAM_ERROR)."""

    error_type: ToolErrorType = "UPSTREAM_ERROR"
