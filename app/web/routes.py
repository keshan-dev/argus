"""API routes for member insights and team overviews (P5-001, Issue #33).

Every member route takes the MemberGuard dependency from app.web.auth (FR-028).
Team overview enforces actor team membership. All question types are validated
strictly against DEC-007 (current_work, blockers, risks).
"""

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.agent.orchestrator import run_agent
from app.agent.planner import build_plan
from app.agent.team_overview import generate_team_overview
from app.schemas.insight import MemberInsight, TeamOverview
from app.web.auth import ActorDep, DbDep, MemberGuard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Insights & Teams"])


@router.get("/members/{member_id}/insight", response_model=MemberInsight)
async def get_member_insight(
    member_id: int,
    question: str = Query(..., description="Question type: current_work, blockers, or risks"),
    member: MemberGuard = None,
    actor: ActorDep = None,
    db: DbDep = None,
) -> MemberInsight:
    """Retrieve member insight for a specific question type (FR-014, FR-028, DEC-007)."""
    # 1. Validate question type (raises 422 InvalidQuestionTypeError if unknown)
    plan = build_plan(question)

    # 2. MemberGuard already checked login (401), user existence (404), and team access (403).
    # Execute full agent pipeline stages S1 through S6
    insight = await run_agent(
        session=db,
        subject_user_id=member.id,
        team_id=member.team_id,
        question_type=plan.question_type,
        actor_user_id=actor.id,
    )
    return insight


@router.get("/teams/{team_id}/overview", response_model=TeamOverview)
def get_team_overview(
    team_id: int,
    actor: ActorDep,
    db: DbDep,
) -> TeamOverview:
    """Retrieve team overview status and member breakdowns (FR-025, Gap G6)."""
    # 1. Verify actor has permission to view this team
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

    # 2. Generate deterministic overview from database and findings rules
    return generate_team_overview(session=db, team_id=team_id)
