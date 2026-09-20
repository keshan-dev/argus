"""Integration adapters, identity resolution, and external clients."""

from app.integrations.errors import (
    AuthError,
    IntegrationError,
    IntegrationTimeoutError,
    NotFoundError,
    RateLimitError,
    UpstreamError,
)
from app.integrations.http import HttpClient
from app.integrations.identity_loader import (
    IdentityMapError,
    load_identity_map,
    parse_identity_map,
)

__all__ = [
    "AuthError",
    "HttpClient",
    "IdentityMapError",
    "IntegrationError",
    "IntegrationTimeoutError",
    "NotFoundError",
    "RateLimitError",
    "UpstreamError",
    "load_identity_map",
    "parse_identity_map",
]
