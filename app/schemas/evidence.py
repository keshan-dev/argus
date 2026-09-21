"""Evidence schemas for S3 evidence builder (P4-001)."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class EntityType(StrEnum):
    work_item = "work_item"
    pull_request = "pull_request"
    commit = "commit"
    review = "review"


class SourceState(StrEnum):
    fresh = "fresh"
    stale = "stale"


class EvidenceItem(BaseModel):
    id: str
    source: Literal["jira", "github"]
    entity_type: EntityType | str
    entity_key: str
    source_url: str | None = None
    summary: str
    excerpt: str | None = None
    observed_at: datetime
    retrieved_at: datetime
    source_state: SourceState | str = SourceState.fresh


class EvidenceSet(BaseModel):
    items: tuple[EvidenceItem, ...] = Field(default_factory=tuple)
    truncated: bool = False
    excluded_null_actor: int = 0
    excluded_unavailable_source: int = 0
    excluded_duplicate: int = 0
