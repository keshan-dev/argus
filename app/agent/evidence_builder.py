"""Build a deterministic, sanitized evidence set from retrieval results (P4-001)."""

import re
from datetime import UTC, datetime
from typing import Any

from app.agent.orchestrator import AgentRunContext
from app.schemas.evidence import (
    EntityType,
    EvidenceItem,
    EvidenceSet,
    SourceState,
)

MAX_EVIDENCE_ITEMS = 50
MAX_EXCERPT_LENGTH = 500

_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_CONTROL_PATTERN = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def _sanitize_excerpt(value: str | None) -> str | None:
    """Remove URLs and control characters, then cap untrusted text."""
    if not value:
        return None

    cleaned = _URL_PATTERN.sub("", value)
    cleaned = _CONTROL_PATTERN.sub(" ", cleaned)
    cleaned = " ".join(cleaned.split())
    cleaned = cleaned[:MAX_EXCERPT_LENGTH].strip()

    return cleaned or None


def _source_state(
    context: AgentRunContext,
    source: str,
) -> SourceState | None:
    """Return the source state, or None if health is missing/unavailable."""
    for health in context.health:
        if health.source == source:
            if health.state == "unavailable":
                return None
            return SourceState(health.state)

    # The orchestrator's policy is fail-closed when health is missing.
    return None


def _work_item_summary(item: Any) -> str:
    """Create a summary from normalized structured fields only."""
    return (
        f"Jira work item {item.external_id}: "
        f"status={item.status}; "
        f"priority={item.priority or 'unspecified'}; "
        f"flagged={'yes' if item.is_flagged else 'no'}"
    )


def _pull_request_summary(item: Any) -> str:
    """Create a summary from normalized structured fields only."""
    return (
        f"GitHub pull request #{item.number} in {item.repo_full_name}: "
        f"state={item.state}; "
        f"review={item.review_state}; "
        f"checks={item.checks_state}; "
        f"draft={'yes' if item.is_draft else 'no'}"
    )


def build_evidence(context: AgentRunContext) -> EvidenceSet:
    """Build a sanitized, deduplicated, ranked evidence set."""
    retrieval = context.retrieval
    now = datetime.now(UTC)

    candidates: list[tuple[int, datetime, EvidenceItem]] = []
    seen: set[tuple[str, str, str]] = set()

    excluded_null_actor = 0
    excluded_unavailable_source = 0
    excluded_duplicate = 0

    jira_state = _source_state(context, "jira")
    github_state = _source_state(context, "github")

    # Jira work items
    for item in retrieval.work_items:
        if jira_state is None:
            excluded_unavailable_source += 1
            continue

        if item.assignee_user_id is None:
            excluded_null_actor += 1
            continue

        entity_key = str(item.external_id)
        dedupe_key = ("jira", "work_item", entity_key)

        if dedupe_key in seen:
            excluded_duplicate += 1
            continue
        seen.add(dedupe_key)

        observed_at = item.source_updated_at
        evidence = EvidenceItem(
            id="",
            source="jira",
            entity_type=EntityType.work_item,
            entity_key=entity_key,
            source_url=item.source_url,
            summary=_work_item_summary(item),
            excerpt=None,
            observed_at=observed_at,
            retrieved_at=item.retrieved_at or now,
            source_state=jira_state,
        )

        # More recent records rank first; Jira records precede GitHub on ties.
        candidates.append((0, observed_at, evidence))

    # GitHub pull requests
    for item in retrieval.pull_requests:
        if github_state is None:
            excluded_unavailable_source += 1
            continue

        if item.author_user_id is None:
            excluded_null_actor += 1
            continue

        entity_key = str(item.number)
        dedupe_key = ("github", "pull_request", entity_key)

        if dedupe_key in seen:
            excluded_duplicate += 1
            continue
        seen.add(dedupe_key)

        observed_at = item.source_updated_at
        evidence = EvidenceItem(
            id="",
            source="github",
            entity_type=EntityType.pull_request,
            entity_key=entity_key,
            source_url=item.source_url,
            summary=_pull_request_summary(item),
            excerpt=_sanitize_excerpt(item.body_excerpt),
            observed_at=observed_at,
            retrieved_at=item.retrieved_at or now,
            source_state=github_state,
        )

        candidates.append((1, observed_at, evidence))

    # Deterministic ranking: newest first, then source/entity ordering.
    candidates.sort(
        key=lambda candidate: (
            -candidate[1].timestamp(),
            candidate[0],
            str(candidate[2].entity_key),
        )
    )

    truncated = len(candidates) > MAX_EVIDENCE_ITEMS
    selected = candidates[:MAX_EVIDENCE_ITEMS]

    # Assign IDs only after ranking and truncation, so they are contiguous.
    final_items = tuple(
        item.model_copy(update={"id": f"ev_{index}"})
        for index, (_, _, item) in enumerate(selected, start=1)
    )

    return EvidenceSet(
        items=final_items,
        truncated=truncated,
        excluded_null_actor=excluded_null_actor,
        excluded_unavailable_source=excluded_unavailable_source,
        excluded_duplicate=excluded_duplicate,
    )
