"""Scheduled synchronization runner and concurrency controller (P2-010, Issue #48).

Runs ingestion automatically on an interval defined by SYNC_INTERVAL_MINUTES.
Enforces concurrency control so identical (source, scope) syncs never overlap,
and recovers from stuck running states after STUCK_SYNC_TIMEOUT_MINUTES (DEC-016).
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import (
    SCHEDULER_ENABLED,
    STUCK_SYNC_TIMEOUT_MINUTES,
    SYNC_INTERVAL_MINUTES,
    settings,
)
from app.db import get_sync_session
from app.models.operations import SyncRun
from app.sync import sync_github, sync_jira

logger = logging.getLogger("argus.scheduler")


def recover_stuck_syncs(
    session: Session,
    source: str,
    scope: str,
    timeout_minutes: int = STUCK_SYNC_TIMEOUT_MINUTES,
    now: datetime | None = None,
) -> bool:
    """Check if a sync is currently running.

    If a sync has been running longer than timeout_minutes, it is marked as failed
    due to timeout so subsequent syncs are not blocked indefinitely. Returns True
    if a sync is still legitimately running and should not be started again.
    """
    current_time = now or datetime.now(UTC)
    cutoff = current_time - timedelta(minutes=timeout_minutes)

    stmt = select(SyncRun).where(
        SyncRun.source == source,
        SyncRun.scope == scope,
        SyncRun.status == "running",
    )
    running_runs = session.scalars(stmt).all()

    has_active_run = False
    for r in running_runs:
        # Check if stuck
        started_at = r.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)

        if started_at < cutoff:
            logger.warning(
                "SyncRun %d for (%s, %s) stuck since %s; marking failed (timeout)",
                r.id,
                source,
                scope,
                started_at,
            )
            r.status = "failed"
            r.error_type = "TIMEOUT"
            r.error_detail = "Sync marked as timed out / stuck after timeout period"
            r.finished_at = current_time
            session.commit()
        else:
            has_active_run = True

    return has_active_run


def run_scheduled_tick(
    session: Session,
    team_id: int = 1,
    gh_scope: str = "keshan-dev/argus",
    jira_scope: str = "ALL",
    stuck_timeout_minutes: int = STUCK_SYNC_TIMEOUT_MINUTES,
) -> dict[str, Any]:
    """Execute one scheduled sync tick across GitHub and Jira with concurrency guards."""
    results: dict[str, Any] = {"github": None, "jira": None}

    # 1. GitHub sync guard
    is_gh_running = recover_stuck_syncs(
        session=session,
        source="github",
        scope=gh_scope,
        timeout_minutes=stuck_timeout_minutes,
    )
    if is_gh_running:
        logger.warning("GitHub sync for %s already running; skipping tick", gh_scope)
        results["github"] = "skipped_running"
    else:
        try:
            gh_run = sync_github(session, team_id=team_id, scope=gh_scope)
            results["github"] = gh_run.status
        except Exception as exc:
            logger.error("Error during scheduled GitHub sync: %s", exc)
            results["github"] = "failed"

    # 2. Jira sync guard
    is_jira_running = recover_stuck_syncs(
        session=session,
        source="jira",
        scope=jira_scope,
        timeout_minutes=stuck_timeout_minutes,
    )
    if is_jira_running:
        logger.warning("Jira sync for %s already running; skipping tick", jira_scope)
        results["jira"] = "skipped_running"
    else:
        try:
            jira_run = sync_jira(session, team_id=team_id, scope=jira_scope)
            results["jira"] = jira_run.status
        except Exception as exc:
            logger.error("Error during scheduled Jira sync: %s", exc)
            results["jira"] = "failed"

    return results


async def scheduler_loop(
    interval_seconds: float,
    stop_event: asyncio.Event,
    team_id: int = 1,
) -> None:
    """Asynchronous background loop that executes ticks until stop_event is set."""
    logger.info("Scheduler loop started with interval of %.1f seconds", interval_seconds)
    while not stop_event.is_set():
        try:
            session = get_sync_session()
            try:
                run_scheduled_tick(session, team_id=team_id)
            finally:
                session.close()
        except Exception as exc:
            logger.error("Unexpected error in scheduler loop: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            # Expected timeout when stop_event is not set: proceed to next tick
            pass

    logger.info("Scheduler loop stopped.")


def start_scheduler_task(
    interval_minutes: int | None = None,
    enabled: bool | None = None,
    team_id: int = 1,
) -> tuple[asyncio.Task[None] | None, asyncio.Event | None]:
    """Start the scheduler background task if enabled."""
    is_enabled = (
        enabled
        if enabled is not None
        else (settings.scheduler_enabled if settings else SCHEDULER_ENABLED)
    )
    if not is_enabled:
        logger.info("Scheduler is disabled via configuration.")
        return None, None

    interval = (
        interval_minutes
        if interval_minutes is not None
        else (settings.sync_interval_minutes if settings else SYNC_INTERVAL_MINUTES)
    )
    interval_sec = max(1.0, interval * 60.0)

    stop_event = asyncio.Event()
    task = asyncio.create_task(
        scheduler_loop(
            interval_seconds=interval_sec,
            stop_event=stop_event,
            team_id=team_id,
        )
    )
    return task, stop_event


async def stop_scheduler_task(
    task: asyncio.Task[None] | None,
    stop_event: asyncio.Event | None,
) -> None:
    """Signal stop_event and cleanly cancel and await scheduler task."""
    if stop_event:
        stop_event.set()
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
