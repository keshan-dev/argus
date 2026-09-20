"""FastAPI application entry point.

P0-003 scope is the skeleton only: the app object and a health endpoint. Routers,
models, tools and agent code arrive in later phases.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from pydantic import BaseModel

from app.config import get_settings
from app.scheduler import start_scheduler_task, stop_scheduler_task


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify application configuration and manage scheduler background task."""
    settings = get_settings()
    task, stop_event = start_scheduler_task(enabled=settings.scheduler_enabled)
    try:
        yield
    finally:
        await stop_scheduler_task(task, stop_event)


app = FastAPI(
    title="ARGUS",
    description="Evidence-based engineering team intelligence agent",
    version="0.1.0",
    lifespan=lifespan,
)


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
