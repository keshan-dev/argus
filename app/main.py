"""FastAPI application entry point.

Wires the health endpoint, the scheduler lifespan and the auth routes. Member-data
routes arrive in P5-001 and MUST take the MemberGuard dependency from app.web.auth.
"""

import shutil
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import get_settings
from app.scheduler import start_scheduler_task, stop_scheduler_task
from app.web.auth import auth_router
from app.web.routes import router as api_router


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

static_dir = Path(__file__).resolve().parent / "web" / "static"
fonts_src = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "headref-ui-pack"
    / "app"
    / "web"
    / "static"
    / "fonts"
)
fonts_dst = static_dir / "fonts"
if fonts_src.exists() and not fonts_dst.exists():
    shutil.copytree(fonts_src, fonts_dst)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.include_router(auth_router)
app.include_router(api_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Redirect unauthenticated browser requests to /login, while preserving API 401."""
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        if not request.url.path.startswith("/api"):
            next_url = request.url.path
            if request.url.query:
                next_url = f"{next_url}?{request.url.query}"
            return RedirectResponse(
                url=f"/login?next={next_url}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


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
