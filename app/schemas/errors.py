"""Error contracts for tool calls and upstream integrations (P1-002, Issue #8)."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

ToolErrorType = Literal[
    "TIMEOUT",
    "NOT_FOUND",
    "UPSTREAM_ERROR",
    "SCHEMA_INVALID",
    "RATE_LIMITED",
    "AUTH_FAILED",
]


class ToolFailure(BaseModel):
    """Failure response contract for read tools and integrations.

    Tools return a typed failure instead of raising exceptions or returning empty lists.
    """

    tool_id: str = Field(description="Identifier of the tool that encountered the failure")
    error_type: ToolErrorType = Field(description="Structured category of failure")
    detail: str = Field(description="Human readable explanation without secrets")
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when failure occurred in UTC",
    )
