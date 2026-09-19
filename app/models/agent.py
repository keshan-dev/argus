"""Agent execution and insight cache models (DATA_AND_EVIDENCE.md 6.3, FR-024, FR-031)."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Insight(Base):
    """A cached validated insight answer, keyed by evidence hash (FR-031)."""

    __tablename__ = "insight"
    __table_args__ = (
        Index("ix_insight_evidence_hash", "evidence_hash"),
        Index("ix_insight_subject_question", "subject_app_user_id", "question_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_app_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # question_type: current_work, blockers, risks
    question_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AgentRun(Base):
    """Audit record of every agent execution (FR-024).

    Note: Evidence is not a standalone table in the MVP. The evidence set is stored
    as JSON inside evidence_set (DEC-004, DATA_AND_EVIDENCE.md 6.3).
    """

    __tablename__ = "agent_run"
    __table_args__ = (Index("ix_agent_run_subject_created", "subject_app_user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_app_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True, index=True
    )
    subject_app_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_type: Mapped[str] = mapped_column(String(64), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Audited execution artifacts
    evidence_set: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    source_health: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_model_output: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    validated_output: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    dropped_claims: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)

    # Operational metrics
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
