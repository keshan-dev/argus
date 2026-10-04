"""Tests for the member insight and team overview routes (P5-001, Issue #33).

Uses a real in-memory SQLite database, the same pattern as test_tools.py and
test_orchestrator.py, with StaticPool and check_same_thread=False so the same
connection survives across FastAPI's worker thread for sync dependencies.
Without this, SQLite raises "objects created in a thread can only be used in
that same thread" as soon as a route's sync dependency runs in a different
thread than the fixture that created the engine.

The LLM is never called in these tests: the unavailable-source case closes the
gate before stage S4, so it exercises the full request/response cycle without
needing Ollama up.
"""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.canonical import AppUser, Organization, Team
from app.models.operations import SyncRun
from app.web import auth
from app.web.auth import auth_router
from app.web.routes import router as api_router


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """An isolated in-memory SQLite database session, shared across threads.

    StaticPool keeps 1 connection alive for the whole engine, and
    check_same_thread=False allows FastAPI's worker thread (used for sync
    route dependencies under TestClient) to use it safely.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def app_with_db(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """A test app wired to the real routes, with get_db overridden to our test session."""

    def fake_db() -> Generator[Session, None, None]:
        yield db_session

    application = FastAPI()
    application.include_router(auth_router)
    application.include_router(api_router)
    application.dependency_overrides[auth.get_db] = fake_db
    return application


@pytest.fixture
def client(app_with_db: FastAPI) -> TestClient:
    """A test client that keeps cookies between requests."""
    return TestClient(app_with_db)


def _seed_team(session: Session) -> tuple[Team, AppUser, AppUser, AppUser]:
    """2 active members on 1 team, plus 1 member on a different team."""
    org = Organization(name="Test Org")
    session.add(org)
    session.flush()

    team = Team(organization_id=org.id, name="Platform")
    other_team = Team(organization_id=org.id, name="Other")
    session.add_all([team, other_team])
    session.flush()

    alice = AppUser(organization_id=org.id, team_id=team.id, display_name="Alice", is_active=True)
    bob = AppUser(organization_id=org.id, team_id=team.id, display_name="Bob", is_active=True)
    carol = AppUser(
        organization_id=org.id, team_id=other_team.id, display_name="Carol", is_active=True
    )
    session.add_all([alice, bob, carol])
    session.flush()

    return team, alice, bob, carol


def _seed_fresh_sync(session: Session, source: str) -> None:
    """A successful sync finished just now, so get_source_health reports 'fresh'."""
    now = datetime.now(UTC)
    run = SyncRun(
        source=source,
        scope="test-team",
        status="success",
        started_at=now - timedelta(minutes=5),
        finished_at=now,
    )
    session.add(run)
    session.flush()


def _log_in(client: TestClient, user_id: int) -> None:
    response = client.post("/api/auth/login", json={"user_id": user_id})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/members/{member_id}/insight
# ---------------------------------------------------------------------------


def test_member_insight_requires_login(client: TestClient, db_session: Session) -> None:
    """An anonymous request is never served member data."""
    _, alice, _, _ = _seed_team(db_session)

    response = client.get(f"/api/members/{alice.id}/insight?question=current_work")

    assert response.status_code == 401


def test_member_insight_cross_team_is_403(client: TestClient, db_session: Session) -> None:
    """A member on a different team is not visible, even with sources healthy."""
    _, alice, _, carol = _seed_team(db_session)
    _seed_fresh_sync(db_session, "jira")
    _seed_fresh_sync(db_session, "github")
    _log_in(client, alice.id)

    response = client.get(f"/api/members/{carol.id}/insight?question=current_work")

    assert response.status_code == 403


def test_member_insight_unknown_member_is_404(client: TestClient, db_session: Session) -> None:
    """A member id that does not exist answers 404, not 403 or 500."""
    _, alice, _, _ = _seed_team(db_session)
    _log_in(client, alice.id)

    response = client.get("/api/members/999999/insight?question=current_work")

    assert response.status_code == 404


def test_member_insight_invalid_question_is_422(client: TestClient, db_session: Session) -> None:
    """An invalid question type is rejected by the planner before any tool runs."""
    _, alice, bob, _ = _seed_team(db_session)
    _seed_fresh_sync(db_session, "jira")
    _seed_fresh_sync(db_session, "github")
    _log_in(client, alice.id)

    response = client.get(f"/api/members/{bob.id}/insight?question=everything")

    assert response.status_code == 422


def test_member_insight_unavailable_source_is_unknown(
    client: TestClient, db_session: Session
) -> None:
    """No sync has ever run, so both sources are unavailable and the gate closes.

    FR-023: the answer is UNKNOWN, with the reason, never a silent empty result.
    The run never reaches the LLM, since the gate closes before stage S4.
    """
    _, alice, bob, _ = _seed_team(db_session)
    _log_in(client, alice.id)

    response = client.get(f"/api/members/{bob.id}/insight?question=current_work")

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == bob.id
    assert data["likely_current_work"]["classification"] == "unknown"
    assert data["likely_current_work"]["confidence"] == "UNKNOWN"
    assert "Cannot be established" in data["likely_current_work"]["claim"]
    assert data["unknowns"]
    # NFR-020: per-source freshness is present even in the unknown case.
    assert "jira" in data["last_synced"]
    assert "github" in data["last_synced"]
    assert len(data["source_health"]) == 2


# ---------------------------------------------------------------------------
# GET /api/teams/{team_id}/overview
# ---------------------------------------------------------------------------


def test_team_overview_requires_login(client: TestClient, db_session: Session) -> None:
    """An anonymous request is never served team data."""
    team, _, _, _ = _seed_team(db_session)

    response = client.get(f"/api/teams/{team.id}/overview")

    assert response.status_code == 401


def test_team_overview_other_team_is_403(client: TestClient, db_session: Session) -> None:
    """An actor may only view their own team's overview."""
    team, alice, _, carol = _seed_team(db_session)
    _log_in(client, carol.id)

    response = client.get(f"/api/teams/{team.id}/overview")

    assert response.status_code == 403


def test_team_overview_unknown_team_is_404(client: TestClient, db_session: Session) -> None:
    """A team id that does not exist answers 404, checked before the team-match 403."""
    _, alice, _, _ = _seed_team(db_session)
    _log_in(client, alice.id)

    response = client.get("/api/teams/999999/overview")

    assert response.status_code == 404


def test_team_overview_unavailable_source_is_unknown_never_on_track(
    client: TestClient, db_session: Session
) -> None:
    """FR-025: a member with unavailable required source data shows unknown,
    never on_track, for every member on the team.
    """
    team, alice, bob, _ = _seed_team(db_session)
    _log_in(client, alice.id)

    response = client.get(f"/api/teams/{team.id}/overview")

    assert response.status_code == 200
    data = response.json()
    assert data["team_id"] == team.id
    assert len(data["members"]) == 2
    for member in data["members"]:
        assert member["status"] == "unknown"
        assert member["status"] != "on_track"
        assert member["state_reason"]
        # NFR-020: per-source freshness present even when unknown.
        assert member["last_synced"]
        assert member["source_health"]


def test_team_overview_healthy_sources_give_a_real_status(
    client: TestClient, db_session: Session
) -> None:
    """With both sources synced, the response is well-formed per member.

    Note: get_source_health (T-007) computes age from last_success_at, which
    SQLite returns as a naive datetime even when stored as timezone-aware.
    Subtracting it from an aware datetime.now(UTC) raises, so T-007 answers
    UPSTREAM_ERROR here even though a sync was seeded. This does not happen
    against Postgres in production. Flagged in WORKLOG.md as a discovered
    issue for Keshan; not fixed here since get_source_health.py is his file.
    """
    team, alice, bob, _ = _seed_team(db_session)
    _seed_fresh_sync(db_session, "jira")
    _seed_fresh_sync(db_session, "github")
    _log_in(client, alice.id)

    response = client.get(f"/api/teams/{team.id}/overview")

    assert response.status_code == 200
    data = response.json()
    assert len(data["members"]) == 2
    for member in data["members"]:
        assert member["status"] in ("on_track", "needs_attention", "blocked", "unknown")
        assert "source_health" in member
        assert "last_synced" in member
