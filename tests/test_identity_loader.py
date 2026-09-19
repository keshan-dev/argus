"""Unit tests for the identity map parser and database loader (P1-005, Issue #11)."""

from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.integrations.identity_loader import (
    IdentityMapError,
    load_identity_map,
    parse_identity_map,
)
from app.models.canonical import AppUser
from app.models.identity import IdentityLink, UnmatchedEntity


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory database session for loader tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_parse_valid_identity_map_file() -> None:
    """Verify seed/identity_map.yml parses and validates successfully."""
    file_path = Path("seed/identity_map.yml")
    assert file_path.is_file(), "seed/identity_map.yml must exist"

    parsed = parse_identity_map(file_path)
    assert len(parsed.people) >= 2

    names = [p.display_name for p in parsed.people]
    assert "Keshan" in names
    assert "Isiwara" in names

    keshan = next(p for p in parsed.people if p.display_name == "Keshan")
    assert keshan.role_label == "Backend Engineer"
    assert len(keshan.accounts) == 2

    integrations = {a.integration for a in keshan.accounts}
    assert integrations == {"github", "jira"}


def test_parse_identity_map_duplicate_external_id() -> None:
    """A duplicate external ID across two people fails with a clear error naming both."""
    raw_yaml = """
people:
  - display_name: Keshan
    accounts:
      - integration: github
        external_id: "12345678"
        external_handle: keshan-dev
  - display_name: Imposter
    accounts:
      - integration: github
        external_id: "12345678"
        external_handle: imposter-dev
"""
    with pytest.raises(IdentityMapError) as exc_info:
        parse_identity_map(raw_yaml)

    msg = str(exc_info.value)
    assert "Duplicate external ID '12345678'" in msg
    assert "Keshan" in msg
    assert "Imposter" in msg


def test_parse_identity_map_malformed_yaml() -> None:
    """A malformed file fails with a clear error naming the problem line."""
    bad_yaml = """
people:
  - display_name: Keshan
    accounts: [unclosed list
"""
    with pytest.raises(IdentityMapError) as exc_info:
        parse_identity_map(bad_yaml)

    msg = str(exc_info.value)
    assert "Malformed YAML on line" in msg


def test_parse_identity_map_invalid_schema() -> None:
    """Schema validation errors (such as invalid integration type) are rejected."""
    invalid_integration = """
people:
  - display_name: Keshan
    accounts:
      - integration: bitbucket
        external_id: "1234"
        external_handle: keshan-bb
"""
    with pytest.raises(IdentityMapError) as exc_info:
        parse_identity_map(invalid_integration)

    assert "schema validation failed" in str(exc_info.value)


def test_load_identity_map_idempotency(db_session: Session) -> None:
    """Loader creates identity_link rows with manual/HIGH and does not duplicate on re-run."""
    map_yaml = """
people:
  - display_name: Keshan
    role_label: Backend Engineer
    accounts:
      - integration: github
        external_id: "12345678"
        external_handle: keshan-dev
      - integration: jira
        external_id: "5f3a1b2c3d4e"
        external_handle: Keshan P.
  - display_name: Isiwara
    role_label: Frontend Engineer
    accounts:
      - integration: github
        external_id: "87654321"
        external_handle: isiwara-dev
"""
    # First execution: create users and links
    links_1 = load_identity_map(db_session, map_yaml)
    assert len(links_1) == 3

    users = db_session.scalars(select(AppUser)).all()
    assert len(users) == 2

    links = db_session.scalars(select(IdentityLink)).all()
    assert len(links) == 3

    for link in links:
        assert link.match_method == "manual"
        assert link.confidence == "HIGH"
        assert link.verified_at is not None

    # Second execution: re-running does not duplicate rows (idempotency)
    links_2 = load_identity_map(db_session, map_yaml)
    assert len(links_2) == 3

    users_after = db_session.scalars(select(AppUser)).all()
    assert len(users_after) == 2

    links_after = db_session.scalars(select(IdentityLink)).all()
    assert len(links_after) == 3


def test_load_identity_map_resolves_unmatched_entity(db_session: Session) -> None:
    """Loading identity map marks pre-existing unmatched entity records as resolved."""
    # Pre-seed an unmatched entity
    unmatched = UnmatchedEntity(
        integration="github",
        external_id="12345678",
        external_handle="keshan-dev",
        occurrence_count=1,
    )
    db_session.add(unmatched)
    db_session.flush()
    assert unmatched.resolved_app_user_id is None

    map_yaml = """
people:
  - display_name: Keshan
    role_label: Backend Engineer
    accounts:
      - integration: github
        external_id: "12345678"
        external_handle: keshan-dev
"""
    load_identity_map(db_session, map_yaml)

    db_session.refresh(unmatched)
    assert unmatched.resolved_app_user_id is not None
    user = db_session.scalar(
        select(AppUser).where(AppUser.id == unmatched.resolved_app_user_id)
    )
    assert user is not None
    assert user.display_name == "Keshan"
