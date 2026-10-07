"""Web and API routes for Headref (Phase 5, Issues #33-#38, #49).

Every member route takes the MemberGuard dependency from app.web.auth (FR-028).
Team routes enforce actor team membership. All question types are validated
strictly against DEC-007 (current_work, blockers, risks).
"""

import logging
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select

from app.agent.orchestrator import run_agent
from app.agent.planner import build_plan
from app.agent.team_overview import generate_team_overview
from app.config import get_settings
from app.models.canonical import AppUser, Team
from app.models.identity import IdentityLink, UnmatchedEntity
from app.schemas.errors import ToolFailure
from app.schemas.insight import MemberInsight, TeamOverview
from app.schemas.tools import (
    GetSourceHealthInput,
    LinkedAccount,
    SourceHealthOut,
    TeamMemberOut,
)
from app.tools.get_source_health import get_source_health
from app.web.auth import (
    SESSION_COOKIE,
    SESSION_MAX_AGE_SECONDS,
    ActorDep,
    DbDep,
    MemberGuard,
    load_user,
    sign_session,
)
from app.web.ui_format import signal_rows, templates

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Headref UI & APIs"])


# ---------------------------------------------------------------------------
# API Endpoints (P5-001, P5-007)
# ---------------------------------------------------------------------------


@router.get("/api/members/{member_id}/insight", response_model=MemberInsight)
async def get_member_insight(
    member_id: int,
    question: str = Query(..., description="Question type: current_work, blockers, or risks"),
    member: MemberGuard = None,
    actor: ActorDep = None,
    db: DbDep = None,
) -> MemberInsight:
    """Retrieve member insight for a specific question type (FR-014, FR-028, DEC-007)."""
    plan = build_plan(question)
    return await run_agent(
        session=db,
        subject_user_id=member.id,
        team_id=member.team_id,
        question_type=plan.question_type,
        actor_user_id=actor.id,
    )


@router.get("/api/teams/{team_id}/overview", response_model=TeamOverview)
def get_team_overview(
    team_id: int,
    actor: ActorDep,
    db: DbDep,
) -> TeamOverview:
    """Retrieve team overview status and member breakdowns (FR-025, Gap G6)."""
    if actor.team_id != team_id or actor.team_id is None:
        logger.warning(
            "team access denied: actor_id=%s actor_team=%s requested_team=%s",
            actor.id,
            actor.team_id,
            team_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to view overview for this team",
        )
    return generate_team_overview(session=db, team_id=team_id)


# ---------------------------------------------------------------------------
# UI Page Routes (P5-002, P5-003, P5-004, P5-005, P5-006)
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
@router.get("/teams/{team_id}", response_class=HTMLResponse)
def get_team_page(
    request: Request,
    actor: ActorDep,
    db: DbDep,
    team_id: int | None = None,
) -> HTMLResponse:
    """Team overview dashboard (P5-004, Issue #36)."""
    target_team_id = actor.team_id if team_id is None else team_id
    if target_team_id is None or actor.team_id != target_team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to view overview for this team",
        )

    overview = generate_team_overview(session=db, team_id=target_team_id)
    return templates.TemplateResponse(
        request=request,
        name="team.html",
        context={
            "request": request,
            "actor": actor,
            "overview": overview,
            "team_name": overview.team_name,
            "team_id": target_team_id,
            "unmatched_count": overview.unmatched_count,
            "nav_current": "team",
            "now": datetime.now(UTC),
        },
    )


def _build_team_member_out(db: DbDep, member: Any) -> TeamMemberOut:
    links = []
    if db:
        links = db.scalars(
            select(IdentityLink)
            .where(IdentityLink.app_user_id == member.id)
            .order_by(IdentityLink.id)
        ).all()
    linked_accounts = [
        LinkedAccount(
            integration=link.integration,  # type: ignore[arg-type]
            external_handle=link.external_handle,
            match_method=link.match_method,  # type: ignore[arg-type]
            confidence=link.confidence,  # type: ignore[arg-type]
        )
        for link in links
    ]
    return TeamMemberOut(
        user_id=member.id,
        display_name=member.display_name,
        role_label=getattr(member, "role_label", None),
        is_active=getattr(member, "is_active", True),
        linked_accounts=linked_accounts,
    )


@router.get("/members/{member_id}", response_class=HTMLResponse)
async def get_member_page(
    request: Request,
    member_id: int,
    question: str = "current_work",
    member: MemberGuard = None,
    actor: ActorDep = None,
    db: DbDep = None,
) -> HTMLResponse:
    """Member profile page (P5-002, Issue #34)."""
    if question not in ("current_work", "blockers", "risks"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown question type",
        )

    member_out = _build_team_member_out(db, member)
    insight = await run_agent(
        session=db,
        subject_user_id=member.id,
        team_id=member.team_id,
        question_type=question,
        actor_user_id=actor.id,
    )

    signals = signal_rows(question, get_settings(), insight.source_health)
    unmatched_count = 0
    team_name = f"Team {member.team_id}"
    if db:
        unmatched_count = (
            db.scalar(
                select(func.count(UnmatchedEntity.id)).where(
                    UnmatchedEntity.resolved_app_user_id.is_(None)
                )
            )
            or 0
        )
        if member.team_id:
            team_obj = db.get(Team, member.team_id)
            if team_obj:
                team_name = team_obj.name

    return templates.TemplateResponse(
        request=request,
        name="member.html",
        context={
            "request": request,
            "actor": actor,
            "member": member_out,
            "insight": insight,
            "question": question,
            "is_own": actor.id == member.id,
            "signals": signals,
            "unmatched_count": unmatched_count,
            "team_name": team_name,
            "team_id": member.team_id,
            "nav_current": "member",
            "now": datetime.now(UTC),
        },
    )


@router.get("/members/{member_id}/panel", response_class=HTMLResponse)
async def get_member_panel(
    request: Request,
    member_id: int,
    question: str = "current_work",
    member: MemberGuard = None,
    actor: ActorDep = None,
    db: DbDep = None,
) -> HTMLResponse:
    """Question panel HTML fragment for progressive enhancement tab swap."""
    if question not in ("current_work", "blockers", "risks"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown question type",
        )

    member_out = _build_team_member_out(db, member)
    insight = await run_agent(
        session=db,
        subject_user_id=member.id,
        team_id=member.team_id,
        question_type=question,
        actor_user_id=actor.id,
    )
    signals = signal_rows(question, get_settings(), insight.source_health)

    return templates.TemplateResponse(
        request=request,
        name="partials/question_panel.html",
        context={
            "request": request,
            "member": member_out,
            "insight": insight,
            "question": question,
            "signals": signals,
            "now": datetime.now(UTC),
        },
    )


def _unmatched_source_health(db: Any, team_id: int | None) -> list[SourceHealthOut]:
    """Per-source health for the unmatched page, with a typed failure never hidden.

    A tool failure is not an empty result (rule 9). When the health tool cannot answer,
    every source is reported unavailable with the error type, so the page says "I could
    not look" rather than showing nothing.
    """
    sources: list[Literal["github", "jira"]] = ["github", "jira"]
    if db is None or team_id is None:
        return []

    result = get_source_health(
        session=db,
        input_data=GetSourceHealthInput(team_id=team_id, sources=sources),
    )
    if isinstance(result, ToolFailure):
        logger.warning(
            "Source health unavailable for the unmatched page, team=%s error_type=%s",
            team_id,
            result.error_type,
        )
        return [
            SourceHealthOut(source=src, state="unavailable", last_error_type=result.error_type)
            for src in sources
        ]
    return list(result.sources)


@router.get("/admin/unmatched", response_class=HTMLResponse)
def get_unmatched_page(
    request: Request,
    actor: ActorDep,
    db: DbDep,
) -> HTMLResponse:
    """Unmatched identity queue administrator view (P5-005, Issue #37)."""
    rows = []
    if db:
        rows = db.scalars(
            select(UnmatchedEntity)
            .where(UnmatchedEntity.resolved_app_user_id.is_(None))
            .order_by(UnmatchedEntity.last_seen_at.desc())
        ).all()

    source_health = _unmatched_source_health(db, actor.team_id)
    team_name = "Team"
    if db and actor.team_id:
        team_obj = db.get(Team, actor.team_id)
        if team_obj:
            team_name = team_obj.name

    return templates.TemplateResponse(
        request=request,
        name="unmatched.html",
        context={
            "request": request,
            "actor": actor,
            "rows": rows,
            "source_health": source_health,
            "team_id": actor.team_id,
            "team_name": team_name,
            "unmatched_count": len(rows),
            "nav_current": "unmatched",
            "now": datetime.now(UTC),
        },
    )


# ---------------------------------------------------------------------------
# Login / Logout Page Routes (Login stub)
# ---------------------------------------------------------------------------


@router.get("/login", response_class=HTMLResponse)
def get_login_page(
    request: Request,
    db: DbDep,
) -> HTMLResponse:
    """Render login stub page."""
    users = []
    if db:
        users = db.scalars(
            select(AppUser).where(AppUser.is_active.is_(True)).order_by(AppUser.display_name)
        ).all()
    next_url = request.query_params.get("next", "/")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "users": users,
            "next": next_url,
            "error": None,
        },
    )


@router.post("/login")
async def post_login(
    request: Request,
    response: Response,
    db: DbDep,
) -> Response:
    """Submit login stub form and set signed session cookie."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
        user_id = int(data.get("user_id", 0))
        next_url = str(data.get("next", "/"))
    else:
        body = (await request.body()).decode("utf-8")
        parsed = parse_qs(body)
        user_id = int(parsed.get("user_id", ["0"])[0])
        next_url = parsed.get("next", ["/"])[0]

    user = load_user(db, user_id)
    if user is None or not user.is_active:
        users = []
        if db:
            users = db.scalars(
                select(AppUser).where(AppUser.is_active.is_(True)).order_by(AppUser.display_name)
            ).all()
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "request": request,
                "users": users,
                "next": next_url,
                "error": "Unknown or inactive user",
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    redirect = RedirectResponse(url=next_url, status_code=status.HTTP_303_SEE_OTHER)
    redirect.set_cookie(
        SESSION_COOKIE,
        sign_session(user.id),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return redirect


@router.post("/logout")
@router.get("/logout")
def logout_redirect() -> Response:
    """Log out and redirect to login page."""
    redirect = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    redirect.delete_cookie(SESSION_COOKIE)
    return redirect
