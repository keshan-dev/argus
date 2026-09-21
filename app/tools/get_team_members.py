"""Deterministic read tool T-001: get_team_members (P3-002, Issue #22).

Returns team members with internal user IDs and mapped external accounts
from PostgreSQL. Unresolved unmatched entities are counted for the UI banner.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.canonical import AppUser, Team
from app.models.identity import IdentityLink, UnmatchedEntity
from app.schemas.errors import ToolFailure
from app.schemas.tools import (
    GetTeamMembersInput,
    GetTeamMembersOutput,
    LinkedAccount,
    TeamMemberOut,
)
from app.tools.base import execute_tool_query


def get_team_members(
    session: Session,
    input_data: GetTeamMembersInput,
) -> GetTeamMembersOutput | ToolFailure:
    """Retrieve members for a team and total count of unresolved unmatched accounts."""

    def _query() -> GetTeamMembersOutput | ToolFailure:
        team = session.get(Team, input_data.team_id)
        if not team:
            return ToolFailure(
                tool_id="T-001",
                error_type="NOT_FOUND",
                detail=f"Team with ID {input_data.team_id} does not exist",
            )

        # Query team members
        stmt = select(AppUser).where(AppUser.team_id == input_data.team_id)
        if not input_data.include_inactive:
            stmt = stmt.where(AppUser.is_active.is_(True))
        stmt = stmt.order_by(AppUser.id)
        users = session.scalars(stmt).all()

        members: list[TeamMemberOut] = []
        for user in users:
            links_stmt = (
                select(IdentityLink)
                .where(IdentityLink.app_user_id == user.id)
                .order_by(IdentityLink.id)
            )
            links = session.scalars(links_stmt).all()
            linked_accounts = [
                LinkedAccount(
                    integration=link.integration,  # type: ignore[arg-type]
                    external_handle=link.external_handle,
                    match_method=link.match_method,  # type: ignore[arg-type]
                    confidence=link.confidence,  # type: ignore[arg-type]
                )
                for link in links
            ]
            members.append(
                TeamMemberOut(
                    user_id=user.id,
                    display_name=user.display_name,
                    role_label=user.role_label,
                    is_active=user.is_active,
                    linked_accounts=linked_accounts,
                )
            )

        # Count unresolved external accounts in unmatched queue
        unmatched_stmt = select(func.count(UnmatchedEntity.id)).where(
            UnmatchedEntity.resolved_app_user_id.is_(None)
        )
        unmatched_count = session.scalar(unmatched_stmt) or 0

        return GetTeamMembersOutput(
            members=members,
            unmatched_count=unmatched_count,
        )

    return execute_tool_query("T-001", _query)
