"""FastAPI application entry point.

Wires the health endpoint and the auth routes. Member-data routes arrive in P5-001
and MUST take the MemberGuard dependency from app.web.auth.
"""

from datetime import UTC, datetime

from fastapi import FastAPI
from pydantic import BaseModel

from app.web.auth import auth_router

app = FastAPI(
    title="ARGUS",
    description="Evidence-based engineering team intelligence agent",
    version="0.1.0",
)

app.include_router(auth_router)


class Health(BaseModel):
    """Response contract for the health endpoint."""

    status: str
    service: str
    version: str
    checked_at: datetime


@app.get("/health", response_model=Health)
def health() -> Health:
    """Report that the API process is up.

    This checks the process only. It deliberately does not touch PostgreSQL or
    Ollama: a readiness check over both belongs with the source health tool
    (T-007) in P3-003, which reports per-source freshness rather than a single
    boolean.
    """
    return Health(
        status="ok",
        service="argus",
        version="0.1.0",
        checked_at=datetime.now(UTC),
    )