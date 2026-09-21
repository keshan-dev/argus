"""Deterministic risk detection rules RK-1 through RK-4 (P4-003, Issue #27).

Evaluates the 4 deterministic risk signals required by FR-021 and DATA_AND_EVIDENCE.md 6.9.
CRITICAL MANDATE (FR-021): Every risk statement describes the work item and the dates.
It NEVER describes or judges the person (e.g. 'AUTH-245 is due in 2 days and is still
In Progress', never 'Keshan is behind').
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from app.agent.conflicts import ConflictFinding
from app.config import get_settings
from app.schemas.tools import CommitOut, PullRequestOut, WorkItemLinkOut, WorkItemOut


class RiskFinding(BaseModel):
    """Structured record of a detected risk signal."""

    signal_id: Literal["RK-1", "RK-2", "RK-3", "RK-4"] = Field(
        description="Risk rule identifier"
    )
    description: str = Field(description="Objective risk statement describing work item and dates")
    entity_key: str = Field(description="Natural identifier of affected ticket")
    work_item_id: int | None = Field(
        default=None, description="Internal work item ID if applicable"
    )
    evidence_keys: list[str] = Field(
        default_factory=list, description="Cited natural entity keys backing this risk"
    )


def detect_risks(
    work_items: Sequence[WorkItemOut],
    pull_requests: Sequence[PullRequestOut] = (),
    commits: Sequence[CommitOut] = (),
    links: Sequence[WorkItemLinkOut] = (),
    conflicts: Sequence[ConflictFinding] = (),
    as_of: datetime | None = None,
) -> list[RiskFinding]:
    """Detect all deterministic risks RK-1 to RK-4 across work items and code activity.

    Enforces FR-021: descriptions strictly refer to tickets and timestamps, never individuals.
    """
    settings = get_settings()
    now = as_of or datetime.now(UTC)
    risks: list[RiskFinding] = []

    for item in work_items:
        if item.status == "done":
            continue

        # ---------------------------------------------------------------------
        # RK-1: Due date within DUE_SOON_DAYS and status is not done
        # ---------------------------------------------------------------------
        if item.due_date is not None:
            time_until_due = item.due_date - now
            max_delta = timedelta(days=settings.due_soon_days)
            # Due date within threshold (or overdue)
            if timedelta(seconds=0) <= time_until_due <= max_delta or time_until_due < timedelta(
                seconds=0
            ):
                due_date_str = item.due_date.strftime("%Y-%m-%d")
                if time_until_due < timedelta(seconds=0):
                    days_overdue = int(abs(time_until_due.total_seconds()) // 86400)
                    desc = (
                        f"{item.external_id} is overdue by {days_overdue} day(s) "
                        f"(due {due_date_str}) and is still {item.raw_status}."
                    )
                else:
                    days_left = int(time_until_due.total_seconds() // 86400)
                    desc = (
                        f"{item.external_id} is due in {days_left} day(s) on "
                        f"{due_date_str} and is still {item.raw_status}."
                    )
                risks.append(
                    RiskFinding(
                        signal_id="RK-1",
                        description=desc,
                        entity_key=item.external_id,
                        work_item_id=item.work_item_id,
                        evidence_keys=[item.external_id],
                    )
                )

        # ---------------------------------------------------------------------
        # RK-2: Time in current status exceeds STATUS_STUCK_DAYS
        # ---------------------------------------------------------------------
        time_in_status = now - item.source_updated_at
        if time_in_status > timedelta(days=settings.status_stuck_days):
            stuck_days = int(time_in_status.total_seconds() // 86400)
            risks.append(
                RiskFinding(
                    signal_id="RK-2",
                    description=(
                        f"{item.external_id} has been in status {item.raw_status} for "
                        f"{stuck_days} days without update."
                    ),
                    entity_key=item.external_id,
                    work_item_id=item.work_item_id,
                    evidence_keys=[item.external_id],
                )
            )

        # ---------------------------------------------------------------------
        # RK-3: High priority item with no activity for NO_ACTIVITY_DAYS
        # ---------------------------------------------------------------------
        is_high_priority = item.priority in ["High", "Highest"]
        if is_high_priority:
            # Find latest activity between Jira source_updated_at and any linked code
            latest_activity = item.source_updated_at

            # Check linked PRs
            for pr in pull_requests:
                if pr.source_updated_at and pr.source_updated_at > latest_activity:
                    # Check if PR relates to item
                    if item.external_id in (pr.branch_name or "") or item.external_id in pr.title:
                        latest_activity = pr.source_updated_at

            # Check linked commits
            for c in commits:
                if c.committed_at > latest_activity:
                    in_branch = item.external_id in (c.branch_name or "")
                    in_excerpt = item.external_id in c.message_excerpt
                    if in_branch or in_excerpt:
                        latest_activity = c.committed_at

            inactivity_delta = now - latest_activity
            if inactivity_delta > timedelta(days=settings.no_activity_days):
                inactive_days = int(inactivity_delta.total_seconds() // 86400)
                risks.append(
                    RiskFinding(
                        signal_id="RK-3",
                        description=(
                            f"High priority item {item.external_id} has had no recorded "
                            f"activity for {inactive_days} days."
                        ),
                        entity_key=item.external_id,
                        work_item_id=item.work_item_id,
                        evidence_keys=[item.external_id],
                    )
                )

    # -------------------------------------------------------------------------
    # RK-4: Unresolved Jira / GitHub conflict exists
    # -------------------------------------------------------------------------
    for cf in conflicts:
        risks.append(
            RiskFinding(
                signal_id="RK-4",
                description=f"Unresolved cross-system conflict: {cf.description}",
                entity_key=cf.work_item_external_id,
                work_item_id=cf.work_item_id,
                evidence_keys=list(cf.evidence_keys),
            )
        )

    return risks
