"""Unit tests for Jira normalizer and canonical database loader (P2-005, Issue #16)."""

from collections.abc import Generator
from datetime import UTC, datetime
import logging

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.integrations.jira_normalizer import (
    extract_blocking_dependencies,
    ingest_dependencies,
    ingest_projects,
    ingest_work_items,
    is_issue_flagged,
    map_status,
    normalize_project,
    normalize_work_item,
    parse_datetime,
    upsert_project,
    upsert_work_item,
    upsert_work_item_dependency,
)
from app.models.canonical import Organization, Project
from app.models.work import WorkItem, WorkItemDependency


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_map_status_known_values() -> None:
    """map_status maps standard Jira status names to canonical taxonomy."""
    assert map_status("To Do") == "todo"
    assert map_status("ready for dev") == "todo"
    assert map_status("In Progress") == "in_progress"
    assert map_status("In Review") == "in_review"
    assert map_status("QA") == "in_review"
    assert map_status("Done") == "done"
    assert map_status("Closed") == "done"
    assert map_status("Blocked") == "blocked"
    assert map_status("Impediment") == "blocked"


def test_map_status_category_fallback(caplog: pytest.LogCaptureFixture) -> None:
    """map_status falls back to statusCategory when raw status is unrecognized."""
    with caplog.at_level(logging.WARNING):
        res = map_status("Needs Polish", status_category_key="indeterminate")
        assert res == "in_progress"
        assert "Unmapped Jira status 'Needs Polish'" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        res2 = map_status("Archived Inactive", status_category_key="done")
        assert res2 == "done"
        assert "Unmapped Jira status 'Archived Inactive'" in caplog.text


def test_map_status_unknown_defaults_to_todo_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Completely unknown status defaults to 'todo' and logs a warning."""
    with caplog.at_level(logging.WARNING):
        res = map_status("SuperUnheardOfState")
        assert res == "todo"
        assert "Unmapped Jira status 'SuperUnheardOfState'" in caplog.text


def test_is_issue_flagged() -> None:
    """is_issue_flagged detects impediment flags in standard and custom fields."""
    assert is_issue_flagged({"flagged": True}) is True
    assert is_issue_flagged({"flagged": False}) is False
    assert is_issue_flagged({"customfield_flagged": [{"value": "Impediment"}]}) is True
    assert is_issue_flagged({"customfield_10015": "impediment"}) is True
    assert is_issue_flagged({"summary": "Regular issue"}) is False


def test_normalize_project_pure() -> None:
    """normalize_project produces canonical project dictionary without database."""
    payload = {"id": "10000", "key": "AUTH", "name": "Authentication Service"}
    proj_dict = normalize_project(payload, organization_id=1)
    assert proj_dict["organization_id"] == 1
    assert proj_dict["key"] == "AUTH"
    assert proj_dict["name"] == "Authentication Service"
    assert proj_dict["is_active"] is True

    with pytest.raises(ValueError, match="Project payload missing key"):
        normalize_project({}, organization_id=1)


def test_normalize_work_item_pure() -> None:
    """normalize_work_item extracts attributes, derives status, and guarantees UTC."""
    retrieved = datetime(2026, 9, 20, 15, 0, 0, tzinfo=UTC)
    payload = {
        "id": "10001",
        "key": "AUTH-245",
        "fields": {
            "summary": "Implement session validation seam",
            "status": {
                "name": "In Progress",
                "statusCategory": {"key": "indeterminate"},
            },
            "priority": {"name": "High"},
            "duedate": "2026-09-22",
            "flagged": False,
            "created": "2026-09-15T09:00:00.000+0000",
            "updated": "2026-09-19T14:00:00.000+0000",
        },
    }
    wi_dict = normalize_work_item(
        payload,
        project_id=5,
        retrieved_at=retrieved,
        jira_base_url="https://example.atlassian.net",
    )
    assert wi_dict["project_id"] == 5
    assert wi_dict["external_id"] == "AUTH-245"
    assert wi_dict["title"] == "Implement session validation seam"
    assert wi_dict["status"] == "in_progress"
    assert wi_dict["raw_status"] == "In Progress"
    assert wi_dict["priority"] == "High"
    assert wi_dict["due_date"] == datetime(2026, 9, 22, 0, 0, 0, tzinfo=UTC)
    assert wi_dict["is_flagged"] is False
    assert wi_dict["assignee_app_user_id"] is None
    assert wi_dict["source_url"] == "https://example.atlassian.net/browse/AUTH-245"
    assert wi_dict["retrieved_at"] == retrieved
    assert wi_dict["source_updated_at"] is not None
    assert wi_dict["source_updated_at"].tzinfo == UTC

    with pytest.raises(ValueError, match="Issue payload missing key"):
        normalize_work_item({}, project_id=5)

    with pytest.raises(ValueError, match="missing summary"):
        normalize_work_item({"key": "AUTH-245", "fields": {}}, project_id=5)


def test_extract_blocking_dependencies() -> None:
    """extract_blocking_dependencies maps inward and outward blocks relationships."""
    # Mock items
    auth_245 = WorkItem(id=1, project_id=1, external_id="AUTH-245", title="245", status="open")
    auth_246 = WorkItem(id=2, project_id=1, external_id="AUTH-246", title="246", status="blocked")
    items_by_key = {"AUTH-245": auth_245, "AUTH-246": auth_246}

    # 1. AUTH-245 outward blocks AUTH-246 (so AUTH-246 is blocked by AUTH-245)
    payload_245 = {
        "key": "AUTH-245",
        "fields": {
            "issuelinks": [
                {
                    "type": {"name": "Blocks", "outward": "blocks"},
                    "outwardIssue": {"key": "AUTH-246"},
                }
            ]
        },
    }
    deps_245 = extract_blocking_dependencies(payload_245, items_by_key)
    assert len(deps_245) == 1
    assert deps_245[0]["work_item_id"] == 2  # AUTH-246 is blocked
    assert deps_245[0]["blocked_by_work_item_id"] == 1  # AUTH-245 is blocking

    # 2. AUTH-246 inward is blocked by AUTH-245
    payload_246 = {
        "key": "AUTH-246",
        "fields": {
            "issuelinks": [
                {
                    "type": {"name": "Blocks", "inward": "is blocked by"},
                    "inwardIssue": {"key": "AUTH-245"},
                }
            ]
        },
    }
    deps_246 = extract_blocking_dependencies(payload_246, items_by_key)
    assert len(deps_246) == 1
    assert deps_246[0]["work_item_id"] == 2
    assert deps_246[0]["blocked_by_work_item_id"] == 1


def test_upsert_project_idempotent(db_session: Session) -> None:
    """upsert_project updates name on re-run without duplicating records."""
    org = Organization(name="Keshan Org", key="KES")
    db_session.add(org)
    db_session.flush()

    proj_dict = {
        "organization_id": org.id,
        "key": "AUTH",
        "name": "Auth Service",
        "is_active": True,
    }

    p1 = upsert_project(db_session, proj_dict)
    assert p1.id is not None
    assert len(db_session.scalars(select(Project)).all()) == 1

    # Re-run with updated name
    updated_dict = {**proj_dict, "name": "Authentication Platform"}
    p2 = upsert_project(db_session, updated_dict)
    assert p2.id == p1.id

    projects = db_session.scalars(select(Project)).all()
    assert len(projects) == 1
    assert projects[0].name == "Authentication Platform"


def test_upsert_work_item_idempotent(db_session: Session) -> None:
    """upsert_work_item updates fields on re-run without creating duplicates."""
    org = Organization(name="Keshan Org", key="KES")
    db_session.add(org)
    db_session.flush()

    proj = Project(organization_id=org.id, key="AUTH", name="Auth")
    db_session.add(proj)
    db_session.flush()

    now = datetime.now(UTC)
    wi_dict = {
        "project_id": proj.id,
        "external_id": "AUTH-245",
        "title": "Initial Title",
        "status": "todo",
        "raw_status": "To Do",
        "assignee_app_user_id": None,
        "priority": "Medium",
        "due_date": now,
        "is_flagged": False,
        "source_url": "https://jira/browse/AUTH-245",
        "source_updated_at": now,
        "retrieved_at": now,
    }

    w1 = upsert_work_item(db_session, wi_dict)
    assert w1.id is not None
    assert len(db_session.scalars(select(WorkItem)).all()) == 1

    # Re-run with updated status and title
    updated_dict = {
        **wi_dict,
        "title": "Updated Title",
        "status": "in_progress",
        "raw_status": "In Progress",
    }
    w2 = upsert_work_item(db_session, updated_dict)
    assert w2.id == w1.id

    items = db_session.scalars(select(WorkItem)).all()
    assert len(items) == 1
    assert items[0].title == "Updated Title"
    assert items[0].status == "in_progress"


def test_upsert_work_item_dependency_idempotent(db_session: Session) -> None:
    """upsert_work_item_dependency updates on re-run without duplicate rows."""
    org = Organization(name="Keshan Org", key="KES")
    db_session.add(org)
    db_session.flush()

    proj = Project(organization_id=org.id, key="AUTH", name="Auth")
    db_session.add(proj)
    db_session.flush()

    now = datetime.now(UTC)
    w1 = WorkItem(
        project_id=proj.id,
        external_id="AUTH-245",
        title="W1",
        status="done",
        raw_status="Done",
        source_url="url1",
        source_updated_at=now,
        retrieved_at=now,
    )
    w2 = WorkItem(
        project_id=proj.id,
        external_id="AUTH-246",
        title="W2",
        status="blocked",
        raw_status="Blocked",
        source_url="url2",
        source_updated_at=now,
        retrieved_at=now,
    )
    db_session.add_all([w1, w2])
    db_session.flush()

    dep_dict = {
        "work_item_id": w2.id,
        "blocked_by_work_item_id": w1.id,
        "link_type": "blocks",
        "retrieved_at": now,
    }

    d1 = upsert_work_item_dependency(db_session, dep_dict)
    assert d1.id is not None
    assert len(db_session.scalars(select(WorkItemDependency)).all()) == 1

    # Re-run
    d2 = upsert_work_item_dependency(db_session, dep_dict)
    assert d2.id == d1.id
    assert len(db_session.scalars(select(WorkItemDependency)).all()) == 1


def test_ingest_work_items_skips_malformed(db_session: Session) -> None:
    """ingest_work_items skips invalid records and increments counts without crashing."""
    org = Organization(name="Keshan Org", key="KES")
    db_session.add(org)
    db_session.flush()

    proj = Project(organization_id=org.id, key="AUTH", name="Auth")
    db_session.add(proj)
    db_session.flush()

    payloads = [
        {
            "key": "AUTH-1",
            "fields": {"summary": "Valid issue 1"},
        },
        {
            # Missing summary -> invalid
            "key": "AUTH-2",
            "fields": {},
        },
        {
            "key": "AUTH-3",
            "fields": {"summary": "Valid issue 3"},
        },
    ]

    items, counts = ingest_work_items(db_session, project_id=proj.id, payloads=payloads)
    assert counts.fetched == 3
    assert counts.written == 2
    assert counts.skipped == 1
    assert len(items) == 2

    persisted = db_session.scalars(select(WorkItem)).all()
    assert len(persisted) == 2
    assert {i.external_id for i in persisted} == {"AUTH-1", "AUTH-3"}
