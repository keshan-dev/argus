"""Deterministic read tool T-006: get_work_item_links (P3-002, Issue #22).

Returns stored correlation links between Jira work items and GitHub pull
requests, branches, and commits with derivation methods and confidence levels.
"""

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.work import WorkItem, WorkItemLink
from app.schemas.errors import ToolFailure
from app.schemas.tools import (
    GetWorkItemLinksInput,
    GetWorkItemLinksOutput,
    WorkItemLinkOut,
)
from app.tools.base import execute_tool_query


def get_work_item_links(
    session: Session,
    input_data: GetWorkItemLinksInput,
) -> GetWorkItemLinksOutput | ToolFailure:
    """Retrieve stored correlation links filtered by work item IDs or pull request IDs."""

    def _query() -> GetWorkItemLinksOutput | ToolFailure:
        stmt = select(WorkItemLink, WorkItem).join(
            WorkItem, WorkItemLink.work_item_id == WorkItem.id
        )

        id_conditions = []
        if input_data.work_item_ids:
            id_conditions.append(WorkItemLink.work_item_id.in_(input_data.work_item_ids))
        if input_data.pull_request_ids:
            pr_target_ids = [str(pr_id) for pr_id in input_data.pull_request_ids]
            id_conditions.append(
                and_(
                    WorkItemLink.target_type == "pull_request",
                    WorkItemLink.target_id.in_(pr_target_ids),
                )
            )

        stmt = stmt.where(or_(*id_conditions))

        # Filter by minimum confidence threshold
        if input_data.min_confidence == "HIGH":
            allowed_confidences = ("HIGH",)
        elif input_data.min_confidence == "MEDIUM":
            allowed_confidences = ("HIGH", "MEDIUM")
        else:
            allowed_confidences = ("HIGH", "MEDIUM", "LOW")

        stmt = stmt.where(WorkItemLink.confidence.in_(allowed_confidences))
        stmt = stmt.order_by(WorkItemLink.id)

        results = session.execute(stmt).all()

        links: list[WorkItemLinkOut] = []
        for link, wi in results:
            try:
                target_id_int = int(link.target_id)
            except ValueError:
                # Exclude non-integer target IDs (such as raw branch name strings)
                continue

            links.append(
                WorkItemLinkOut(
                    link_id=link.id,
                    work_item_id=link.work_item_id,
                    work_item_external_id=wi.external_id,
                    target_type=link.target_type,  # type: ignore[arg-type]
                    target_id=target_id_int,
                    link_method=link.link_method,  # type: ignore[arg-type]
                    confidence=link.confidence,  # type: ignore[arg-type]
                    created_at=link.created_at,
                )
            )

        return GetWorkItemLinksOutput(links=links)

    return execute_tool_query("T-006", _query)
