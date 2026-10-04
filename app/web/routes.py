"""Member insight and team overview API routes (P5-001, Issue #33).

Both routes check authorization before doing anything else. The member route uses
the orchestrator's full pipeline (S1-S6, including the narrative). The team route
runs only the deterministic stages (S1-S3 plus the findings engine) per member, with
no LLM call, since it needs a status and evidence rather than a narrative.
"""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session

from app.agent.blockers import detect_blockers
from app.agent.confidence import evaluate_confidence
from app.agent.conflicts import detect_conflicts
from app.agent.evidence_builder import build_evidence
from app.agent.orchestrator import AgentRunContext, run_agent, run_s1_s2
from app.agent.risks import detect_risks
from app.models.canonical import Team
from app.schemas.errors import ToolFailure
from app.schemas.insight import (
    AttentionItem,
    EvidenceItem,
    MemberInsight,
    TeamMemberSummary,
    TeamOverview,
)
from app.schemas.tools import GetTeamMembersInput, TeamMemberOut
from app.tools.get_team_members import get_team_members
from app.web.auth import ActorDep, DbDep, MemberGuard

router = APIRouter(prefix="/api", tags=["Insights & Teams"])


@router.get("/members/{member_id}/insight", response_model=MemberInsight)
async def get_member_insight(
    member_id: int,
    actor: ActorDep,
    subject: MemberGuard,
    db: DbDep,
    question: str = Query(..., description="current_work, blockers, or risks"),
) -> MemberInsight:
    """Return a member's insight for 1 question type (FR-014).

    MemberGuard answers 404 if the member does not exist and 403 if the actor may
    not view them, before anything else runs. An invalid question answers 422,
    raised by app.agent.planner.build_plan inside the orchestrator.
    """
    if subject.team_id is None:
        # Unreachable in practice: MemberGuard already requires a shared, non-null
        # team_id. Kept as a defensive fail-closed check, never trust team_id is set.
        raise HTTPException(status_code=403, detail="Not allowed to view this member")

    return await run_agent(
        db,
        subject_user_id=member_id,
        team_id=subject.team_id,
        question_type=question,
        actor_user_id=actor.id,
    )


def _canonical_evidence(context: AgentRunContext) -> list[EvidenceItem]:
    """Convert 1 run's evidence set to the frozen API EvidenceItem shape.

    Mirrors the conversion in app.agent.orchestrator.run_agent, since S3's evidence
    items (app.schemas.evidence.EvidenceItem) are not the same class as the API's
    app.schemas.insight.EvidenceItem.
    """
    evidence_set = build_evidence(context)
    return [
        EvidenceItem(
            id=ev.id,
            source=ev.source,
            entity_type=str(ev.entity_type),
            entity_key=str(ev.entity_key),
            source_url=ev.source_url or "",
            summary=ev.summary,
            excerpt=ev.excerpt,
            observed_at=ev.observed_at,
            retrieved_at=ev.retrieved_at,
            source_state="fresh" if str(ev.source_state) == "fresh" else "stale",
        )
        for ev in evidence_set.items
    ]


def _attention_items(
    kind: Literal["blocker", "risk"],
    findings: list,
    canonical_evidence: list[EvidenceItem],
    conflicts: list,
    is_truncated: bool,
    as_of: datetime,
) -> list[AttentionItem]:
    """Build AttentionItem rows for a list of detected blockers or risks."""
    claim_type = "declared_blocker" if kind == "blocker" else "due_date"
    items: list[AttentionItem] = []
    for finding in findings:
        matched_evidence = [
            ev
            for ev in canonical_evidence
            if ev.entity_key in finding.evidence_keys
            or any(key in ev.summary for key in finding.evidence_keys)
        ]
        has_conflict = any(c.work_item_external_id == finding.entity_key for c in conflicts)
        confidence = evaluate_confidence(
            matched_evidence,
            claim_type=claim_type,
            has_unresolved_conflict=has_conflict,
            is_truncated=is_truncated,
            as_of=as_of,
        )
        items.append(
            AttentionItem(
                kind=kind,
                claim=finding.description,
                confidence=confidence,
                evidence=matched_evidence,
            )
        )
    return items


def _evaluate_member(session: Session, member: TeamMemberOut, team_id: int) -> TeamMemberSummary:
    """Compute 1 team member's status row, with no LLM call.

    Runs the blockers and risks plans separately (different required sources and
    lookback windows), via the deterministic findings engine only. Either gate
    failing closed means the member is 'unknown', per FR-025: never 'on_track' when
    a required source is unavailable.
    """
    ctx_blockers = run_s1_s2(
        session, subject_user_id=member.user_id, team_id=team_id, question_type="blockers"
    )
    ctx_risks = run_s1_s2(
        session, subject_user_id=member.user_id, team_id=team_id, question_type="risks"
    )

    health = {h.source: h for h in ctx_blockers.health}
    health.update({h.source: h for h in ctx_risks.health})

    if not ctx_blockers.gate.proceed or not ctx_risks.gate.proceed:
        reasons = [*ctx_blockers.gate.reasons, *ctx_risks.gate.reasons]
        return TeamMemberSummary(
            user_id=member.user_id,
            display_name=member.display_name,
            status="unknown",
            state_reason="; ".join(dict.fromkeys(reasons)) or "required data is unavailable",
            attention_items=[],
            last_synced={h.source: h.last_success_at for h in health.values()},
            source_health=list(health.values()),
        )

    blocker_evidence = _canonical_evidence(ctx_blockers)
    risk_evidence = _canonical_evidence(ctx_risks)

    blocker_conflicts = detect_conflicts(
        ctx_blockers.retrieval.work_items,
        ctx_blockers.retrieval.pull_requests,
        ctx_blockers.retrieval.commits,
        ctx_blockers.retrieval.links,
    )
    blockers = detect_blockers(
        ctx_blockers.retrieval.work_items,
        ctx_blockers.retrieval.pull_requests,
        ctx_blockers.retrieval.commits,
        ctx_blockers.retrieval.links,
        as_of=ctx_blockers.started_at,
    )
    risk_conflicts = detect_conflicts(
        ctx_risks.retrieval.work_items,
        ctx_risks.retrieval.pull_requests,
        ctx_risks.retrieval.commits,
        ctx_risks.retrieval.links,
    )
    risks = detect_risks(
        ctx_risks.retrieval.work_items,
        ctx_risks.retrieval.pull_requests,
        ctx_risks.retrieval.commits,
        ctx_risks.retrieval.links,
        conflicts=risk_conflicts,
        as_of=ctx_risks.started_at,
    )

    if blockers:
        member_status: Literal["on_track", "needs_attention", "blocked", "unknown"] = "blocked"
    elif risks:
        member_status = "needs_attention"
    else:
        member_status = "on_track"

    blocker_items = _attention_items(
        "blocker",
        blockers,
        blocker_evidence,
        blocker_conflicts,
        is_truncated=False,
        as_of=ctx_blockers.started_at,
    )
    risk_items = _attention_items(
        "risk",
        risks,
        risk_evidence,
        risk_conflicts,
        is_truncated=False,
        as_of=ctx_risks.started_at,
    )
    attention_items = (blocker_items + risk_items)[:3]

    return TeamMemberSummary(
        user_id=member.user_id,
        display_name=member.display_name,
        status=member_status,
        state_reason=None,
        attention_items=attention_items,
        last_synced={h.source: h.last_success_at for h in health.values()},
        source_health=list(health.values()),
    )


@router.get("/teams/{team_id}/overview", response_model=TeamOverview)
async def get_team_overview(team_id: int, actor: ActorDep, db: DbDep) -> TeamOverview:
    """Return a team's overview: 1 status row per member, no LLM call (FR-025).

    The actor may only view their own team. No MemberGuard equivalent exists for
    teams yet, so this checks actor.team_id directly; flagged in WORKLOG.md for
    review, since app/web/auth.py's authorization rule is otherwise the single
    place this check is written.

    Team existence is checked before the team-match check, so a nonexistent team
    answers 404 rather than 403.
    """
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    if actor.team_id is None or actor.team_id != team_id:
        raise HTTPException(status_code=403, detail="Not allowed to view this team")

    result = get_team_members(db, GetTeamMembersInput(team_id=team_id))
    if isinstance(result, ToolFailure):
        raise HTTPException(status_code=502, detail=f"Could not load team members: {result.detail}")

    members = [_evaluate_member(db, member, team_id) for member in result.members]

    return TeamOverview(
        team_id=team_id,
        members=members,
        generated_at=datetime.now(UTC),
    )
