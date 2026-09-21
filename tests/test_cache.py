"""Unit tests for agent run persistence and insight cache (P4-007, Issue #31)."""

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.agent.cache import (
    compute_evidence_hash,
    get_cached_insight,
    persist_agent_run,
    save_cached_insight,
)
from app.db import Base
from app.models.canonical import AppUser, Organization
from app.schemas.insight import MemberInsight


def test_hash_stability_and_ordering() -> None:
    """Hash must be stable regardless of dictionary key ordering or item order."""
    evidence_a = [
        {"id": "ev_1", "source": "jira", "entity_key": "AUTH-245", "summary": "A"},
        {"id": "ev_2", "source": "github", "entity_key": "182", "summary": "B"},
    ]
    # Inverted key and dictionary ordering
    evidence_b = [
        {"summary": "B", "entity_key": "182", "source": "github", "id": "ev_2"},
        {"summary": "A", "id": "ev_1", "entity_key": "AUTH-245", "source": "jira"},
    ]

    hash_a = compute_evidence_hash("1", "current_work", evidence_a)
    hash_b = compute_evidence_hash("1", "current_work", evidence_b)

    assert hash_a == hash_b


def test_cache_miss_on_changed_evidence() -> None:
    """Different evidence items produce different hash keys."""
    evidence_1 = [{"id": "ev_1", "source": "jira", "entity_key": "AUTH-245"}]
    evidence_2 = [{"id": "ev_1", "source": "jira", "entity_key": "AUTH-246"}]

    hash_1 = compute_evidence_hash(1, "current_work", evidence_1)
    hash_2 = compute_evidence_hash(1, "current_work", evidence_2)

    assert hash_1 != hash_2


def test_cache_miss_on_different_user_or_question() -> None:
    """Different user or question produces different hash keys."""
    evidence = [{"id": "ev_1", "source": "jira", "entity_key": "AUTH-245"}]

    hash_1 = compute_evidence_hash(1, "current_work", evidence)
    hash_2 = compute_evidence_hash(2, "current_work", evidence)
    hash_3 = compute_evidence_hash(1, "blockers", evidence)

    assert hash_1 != hash_2
    assert hash_1 != hash_3


def test_cache_storage_and_retrieval() -> None:
    """Test saving to cache and retrieving valid unexpired insight from database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session: Session = session_factory()

    try:
        # Create organization and user
        org = Organization(name="Test Org", domain="test.com")
        session.add(org)
        session.flush()

        user = AppUser(
            organization_id=org.id,
            email="keshan@example.com",
            full_name="Keshan",
        )
        session.add(user)
        session.flush()

        insight = MemberInsight(
            user_id=user.id,
            summary="Test insight summary.",
            unknowns=[],
        )
        ev_hash = "abc123hash"

        # Cache miss before save
        miss = get_cached_insight(session, user.id, "current_work", ev_hash)
        assert miss is None

        # Save and verify cache hit
        save_cached_insight(session, user.id, "current_work", ev_hash, insight)
        hit = get_cached_insight(session, user.id, "current_work", ev_hash)
        assert hit is not None
        assert hit.summary == "Test insight summary."
        assert hit.user_id == user.id

        # Persist agent run
        now = datetime.now(UTC)
        run = persist_agent_run(
            session=session,
            subject_user_id=user.id,
            question_type="current_work",
            window_start=now,
            window_end=now,
            evidence_set=[{"id": "ev_1"}],
            source_health={"jira": "fresh"},
            input_tokens=100,
            output_tokens=50,
            latency_ms=250,
        )
        assert run is not None
        assert run.subject_app_user_id == user.id
        assert run.input_tokens == 100
        assert run.latency_ms == 250
    finally:
        session.close()