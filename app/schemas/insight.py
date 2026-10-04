"""Evidence, claim, and insight contracts (P1-002, Issue #8)."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.tools import SourceHealthOut, WorkItemOut


class EvidenceItem(BaseModel):
    """Frozen, code-generated evidence unit with a stable identifier within 1 agent run.

    Per DEC-004, the model cites these by ID; it never generates EvidenceItem objects.
    """

    id: str = Field(description="Sequential identifier within 1 run e.g. ev_1")
    source: Literal["jira", "github"] = Field(description="Authoritative source platform")
    entity_type: Literal["work_item", "pull_request", "commit", "review", "work_item_link"] = Field(
        description="Underlying entity type"
    )
    entity_key: str = Field(
        description="Natural identifier e.g. AUTH-245, acme/api#182, or commit sha"
    )
    source_url: str = Field(description="Deep link to source record")
    summary: str = Field(
        description="One factual line generated strictly by application code, never by the model"
    )
    excerpt: str | None = Field(
        default=None,
        description="Untrusted source text, capped at EXCERPT_MAX_CHARS and URL-stripped",
    )
    observed_at: datetime = Field(description="When event occurred at source")
    retrieved_at: datetime = Field(description="When fetched into ARGUS")
    source_state: Literal["fresh", "stale"] = Field(
        description="Freshness state of source at evidence construction time"
    )


class Claim(BaseModel):
    """Structured claim produced by deterministic rules or narrative extraction.

    The model returns evidence_ids only. It MUST NOT return EvidenceItem objects (DEC-004).
    """

    text: str = Field(description="Factual or inferential statement")
    classification: Literal["fact", "inference", "unknown"] = Field(
        description="Epistemic status of claim"
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="IDs citing pre-built evidence set, strictly strings and never objects",
    )

    @property
    def claim(self) -> str:
        """Alias for text for compatibility across codebase contexts."""
        return self.text

    @model_validator(mode="before")
    @classmethod
    def _normalize_claim_text(cls, data: Any) -> Any:
        """Allow claim key as alias for text when parsing dictionaries."""
        if isinstance(data, dict):
            if "text" not in data and "claim" in data:
                data = dict(data)
                data["text"] = data["claim"]
        return data

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def _reject_embedded_objects(cls, v: Any) -> list[str]:
        """Enforce DEC-004: evidence_ids must be string IDs, not embedded evidence objects."""
        if not isinstance(v, list):
            raise ValueError("evidence_ids must be a list of string identifiers")
        for item in v:
            if not isinstance(item, str):
                raise ValueError(
                    f"evidence_ids must only contain string identifiers, got {type(item).__name__}"
                )
        return v


class Insight(BaseModel):
    """A claim joined with resolved evidence items and calculated confidence."""

    claim: str = Field(description="Statement of insight")
    classification: Literal["fact", "inference", "unknown"] = Field(
        description="Epistemic status of insight"
    )
    confidence: Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"] = Field(
        description="Computed confidence level assigned by code, not by the model"
    )
    evidence: list[EvidenceItem] = Field(
        default_factory=list,
        description="Resolved evidence objects backing this claim",
    )
    conflicts: list[str] = Field(
        default_factory=list,
        description="Human-readable conflict notes produced by code",
    )

    @property
    def text(self) -> str:
        """Alias for claim for compatibility across codebase contexts."""
        return self.claim

    @model_validator(mode="before")
    @classmethod
    def _normalize_claim_text(cls, data: Any) -> Any:
        """Allow text key as alias for claim when parsing dictionaries."""
        if isinstance(data, dict):
            if "claim" not in data and "text" in data:
                data = dict(data)
                data["claim"] = data["text"]
        return data


class MemberInsight(BaseModel):
    """Full API response contract for a team member's insight view."""

    user_id: int = Field(description="Internal user ID of subject")
    likely_current_work: Insight | None = Field(
        default=None, description="Primary current work insight if determined"
    )
    assigned: list[WorkItemOut] = Field(
        default_factory=list, description="Currently assigned work items"
    )
    blockers: list[Insight] = Field(default_factory=list, description="Detected blocker insights")
    risks: list[Insight] = Field(default_factory=list, description="Detected risk insights")
    unknowns: list[str] = Field(default_factory=list, description="Explicit unknowns or data gaps")
    last_synced: dict[str, datetime | None] = Field(
        default_factory=dict,
        description="Per-source last successful sync timestamp",
    )
    source_health: list[SourceHealthOut] = Field(
        default_factory=list,
        description="Per-source operational health and availability state",
    )
    summary: str | None = Field(default=None, description="Optional high-level narrative summary")


# --- Team overview contracts (P5-001, Issue #33, FR-025, NFR-020) ---
#
# DRAFT: This schema did not exist before P5-001. It is proposed by Isiwara (Dev 2) and
# needs Keshan's review before merge, since app/schemas/ is frozen and shared. See the
# WORKLOG entry for this task for the explicit flag.
# Field names (state_reason, kind) match the Headref UI pack's template contract,
# docs/UI_IMPLEMENTATION.md section 9.3 gap G6.


class AttentionItem(BaseModel):
    """1 blocker or risk line shown on a member's card in the team overview."""

    kind: Literal["blocker", "risk"] = Field(
        description="Which tab and question type this item links to"
    )
    claim: str = Field(description="Short claim text shown on the card")
    confidence: Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"] = Field(
        description="Computed confidence level assigned by code, not by the model"
    )
    evidence: list[EvidenceItem] = Field(
        default_factory=list,
        description="Evidence backing this item; required unless status is 'unknown'",
    )


class TeamMemberSummary(BaseModel):
    """One team member's row in a team overview response."""

    user_id: int = Field(description="Internal user ID of the member")
    display_name: str = Field(description="Member's display name")
    status: Literal["on_track", "needs_attention", "blocked", "unknown"] = Field(
        description="Overall status for this member. A member with any unavailable "
        "required source MUST be 'unknown', never 'on_track' (FR-025)."
    )
    state_reason: str | None = Field(
        default=None,
        description="Short, code-generated explanation for the status, "
        "especially for 'blocked' or 'unknown'",
    )
    attention_items: list[AttentionItem] = Field(
        default_factory=list,
        description="Up to 3 blocker/risk lines shown on the member's card",
    )
    last_synced: dict[str, datetime | None] = Field(
        default_factory=dict,
        description="Per-source last successful sync timestamp for this member",
    )
    source_health: list[SourceHealthOut] = Field(
        default_factory=list,
        description="Per-source operational health and availability state for this member",
    )


class TeamOverview(BaseModel):
    """Full API response contract for a team's overview view."""

    team_id: int = Field(description="Internal team ID")
    members: list[TeamMemberSummary] = Field(
        default_factory=list, description="Per-member status summaries"
    )
    generated_at: datetime = Field(
        description="When this overview was computed; team overview is not cached"
    )