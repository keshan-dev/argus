from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["Insights & Teams"])

# Allowed question types (must be exactly 3 values, otherwise 422)
VALID_QUESTIONS = {"progress", "risks", "blockers"}

class SourceHealth(BaseModel):
    source_name: str
    last_synced: str
    health_state: str  # healthy, stale, unavailable

class MemberInsightResponse(BaseModel):
    member_id: str
    question: str
    summary: str
    sources: List[SourceHealth]
    fallback_used: bool

class TeamOverviewResponse(BaseModel):
    team_id: str
    overall_status: str  # On Track, Needs Attention, Blocked, Unknown
    members_summary: List[dict]

def can_view_member(member_id: str, current_user_id: str = "user_default") -> bool:
    """Stub for member view authorization check."""
    # In production, check workspace permissions or role bindings
    if member_id == "unauthorized_member":
        return False
    return True

@router.get("/members/{id}/insight", response_model=MemberInsightResponse)
async def get_member_insight(
    id: str, 
    question: str = Query(..., description="Question type: progress, risks, or blockers")
):
    """Retrieves member insight for a specific question type."""
    if question not in VALID_QUESTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid question type. Must be one of: {list(VALID_QUESTIONS)}"
        )
    
    if not can_view_member(id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view insights for this member."
        )

    # Simulated data retrieval & freshness check
    if id == "unknown_source_member":
        sources = [SourceHealth(source_name="github", last_synced="N/A", health_state="unavailable")]
    else:
        sources = [SourceHealth(source_name="github", last_synced="2026-09-24T12:00:00Z", health_state="healthy")]

    return MemberInsightResponse(
        member_id=id,
        question=question,
        summary=f"Member {id} insight summary for {question}.",
        sources=sources,
        fallback_used=False
    )

@router.get("/teams/{id}/overview", response_model=TeamOverviewResponse)
async def get_team_overview(id: str):
    """Retrieves team overview status and member breakdowns."""
    # Simulated team overview calculation
    return TeamOverviewResponse(
        team_id=id,
        overall_status="On Track",
        members_summary=[
            {
                "member_id": "member_1",
                "status": "On Track",
                "sources": [{"source_name": "jira", "last_synced": "2026-09-24T10:00:00Z", "health_state": "healthy"}]
            }
        ]
    )