"""Unit tests for Pydantic contracts and schemas (P1-002, Issue #8)."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.errors import ToolFailure
from app.schemas.insight import Claim, EvidenceItem, Insight, MemberInsight
from app.schemas.tools import (
    CommitOut,
    GetAssignedWorkItemsInput,
    GetAssignedWorkItemsOutput,
    GetCommitsInput,
    GetCommitsOutput,
    GetPullRequestsInput,
    GetPullRequestsOutput,
    GetReviewsInput,
    GetReviewsOutput,
    GetSourceHealthInput,
    GetSourceHealthOutput,
    GetTeamMembersInput,
    GetTeamMembersOutput,
    GetWorkItemLinksInput,
    GetWorkItemLinksOutput,
    LinkedAccount,
    PullRequestOut,
    ReviewOut,
    SourceHealthOut,
    TeamMemberOut,
    WorkItemLinkOut,
    WorkItemOut,
)


def test_tool_failure_read_path_types() -> None:
    """Verify ToolFailure handles all 4 read-path error types."""
    read_path_errors = ["TIMEOUT", "NOT_FOUND", "UPSTREAM_ERROR", "SCHEMA_INVALID"]
    for err in read_path_errors:
        failure = ToolFailure(
            tool_id="T-001",
            error_type=err,  # type: ignore[arg-type]
            detail="Test detail message",
            occurred_at=datetime.now(UTC),
        )
        data = failure.model_dump()
        restored = ToolFailure.model_validate(data)
        assert restored.tool_id == "T-001"
        assert restored.error_type == err
        assert restored.detail == "Test detail message"


def test_t001_get_team_members_roundtrip() -> None:
    """Verify T-001 inputs and outputs round-trip serialize."""
    inp = GetTeamMembersInput(team_id=1, include_inactive=True)
    assert inp.team_id == 1
    assert inp.include_inactive is True

    member = TeamMemberOut(
        user_id=7,
        display_name="Keshan",
        role_label="Backend Engineer",
        is_active=True,
        linked_accounts=[
            LinkedAccount(
                integration="github",
                external_handle="keshan-dev",
                match_method="manual",
                confidence="HIGH",
            ),
            LinkedAccount(
                integration="jira",
                external_handle="Keshan P.",
                match_method="manual",
                confidence="HIGH",
            ),
        ],
    )
    out = GetTeamMembersOutput(members=[member], unmatched_count=1)
    dumped = out.model_dump()
    loaded = GetTeamMembersOutput.model_validate(dumped)
    assert len(loaded.members) == 1
    assert loaded.members[0].display_name == "Keshan"
    assert loaded.unmatched_count == 1


def test_t002_get_assigned_work_items_roundtrip() -> None:
    """Verify T-002 inputs and outputs round-trip serialize."""
    now = datetime.now(UTC)
    inp = GetAssignedWorkItemsInput(
        subject_user_id=7,
        window_start=now,
        window_end=now,
        include_done=False,
        statuses=["in_progress"],
    )
    assert inp.subject_user_id == 7
    assert inp.statuses == ["in_progress"]

    item = WorkItemOut(
        work_item_id=41,
        external_id="AUTH-245",
        title="Refresh token rotation",
        status="in_progress",
        raw_status="In Progress",
        assignee_user_id=7,
        priority="High",
        due_date=now,
        is_flagged=False,
        blocked_by=["AUTH-240"],
        source_url="https://example.atlassian.net/browse/AUTH-245",
        source_updated_at=now,
        retrieved_at=now,
    )
    out = GetAssignedWorkItemsOutput(items=[item])
    dumped = out.model_dump()
    loaded = GetAssignedWorkItemsOutput.model_validate(dumped)
    assert len(loaded.items) == 1
    assert loaded.items[0].external_id == "AUTH-245"
    assert loaded.items[0].blocked_by == ["AUTH-240"]


def test_t003_get_pull_requests_roundtrip() -> None:
    """Verify T-003 inputs and outputs round-trip serialize."""
    now = datetime.now(UTC)
    inp = GetPullRequestsInput(
        subject_user_id=7,
        window_start=now,
        window_end=now,
        states=["open"],
        include_drafts=True,
    )
    assert inp.states == ["open"]

    pr = PullRequestOut(
        pull_request_id=182,
        number=182,
        repo_full_name="acme/api",
        title="feat: add token rotation",
        body_excerpt="Capped body excerpt",
        state="open",
        is_draft=False,
        branch_name="feature/AUTH-245-token",
        author_user_id=7,
        review_state="approved",
        last_review_at=now,
        checks_state="passing",
        created_at=now,
        last_commit_at=now,
        merged_at=None,
        source_url="https://github.com/acme/api/pull/182",
        source_updated_at=now,
        retrieved_at=now,
    )
    out = GetPullRequestsOutput(pull_requests=[pr])
    dumped = out.model_dump()
    loaded = GetPullRequestsOutput.model_validate(dumped)
    assert len(loaded.pull_requests) == 1
    assert loaded.pull_requests[0].repo_full_name == "acme/api"


def test_t004_get_commits_roundtrip() -> None:
    """Verify T-004 inputs and outputs round-trip serialize."""
    now = datetime.now(UTC)
    inp = GetCommitsInput(
        subject_user_id=7,
        window_start=now,
        window_end=now,
        limit=50,
    )
    assert inp.limit == 50

    commit = CommitOut(
        commit_id=10,
        sha="abc123def456",
        repo_full_name="acme/api",
        message_excerpt="AUTH-245: add rotation test",
        branch_name="feature/AUTH-245-token",
        author_user_id=7,
        committed_at=now,
        source_url="https://github.com/acme/api/commit/abc123def456",
        retrieved_at=now,
    )
    out = GetCommitsOutput(commits=[commit], truncated=False)
    dumped = out.model_dump()
    loaded = GetCommitsOutput.model_validate(dumped)
    assert len(loaded.commits) == 1
    assert loaded.commits[0].sha == "abc123def456"
    assert loaded.truncated is False


def test_t005_get_reviews_roundtrip() -> None:
    """Verify T-005 inputs and outputs round-trip serialize."""
    now = datetime.now(UTC)
    inp = GetReviewsInput(
        subject_user_id=7,
        window_start=now,
        window_end=now,
        direction="received",
    )
    assert inp.direction == "received"

    review = ReviewOut(
        review_id=5,
        pull_request_id=182,
        pull_request_number=182,
        repo_full_name="acme/api",
        reviewer_user_id=9,
        state="approved",
        body_excerpt="LGTM",
        submitted_at=now,
        source_url="https://github.com/acme/api/pull/182#pullrequestreview-5",
        retrieved_at=now,
    )
    out = GetReviewsOutput(reviews=[review])
    dumped = out.model_dump()
    loaded = GetReviewsOutput.model_validate(dumped)
    assert len(loaded.reviews) == 1
    assert loaded.reviews[0].state == "approved"


def test_t006_get_work_item_links_validation_and_roundtrip() -> None:
    """Verify T-006 validation requires at least one ID and output round-trips."""
    # Fails when neither ID list is supplied
    with pytest.raises(ValidationError):
        GetWorkItemLinksInput()

    now = datetime.now(UTC)
    inp = GetWorkItemLinksInput(work_item_ids=[41], min_confidence="HIGH")
    assert inp.work_item_ids == [41]
    assert inp.min_confidence == "HIGH"

    link = WorkItemLinkOut(
        link_id=12,
        work_item_id=41,
        work_item_external_id="AUTH-245",
        target_type="pull_request",
        target_id=182,
        link_method="branch_name",
        confidence="HIGH",
        created_at=now,
    )
    out = GetWorkItemLinksOutput(links=[link])
    dumped = out.model_dump()
    loaded = GetWorkItemLinksOutput.model_validate(dumped)
    assert len(loaded.links) == 1
    assert loaded.links[0].target_id == 182


def test_t007_get_source_health_roundtrip() -> None:
    """Verify T-007 inputs and outputs round-trip serialize."""
    now = datetime.now(UTC)
    inp = GetSourceHealthInput(team_id=1, sources=["github", "jira"])
    assert inp.sources == ["github", "jira"]

    health_items = [
        SourceHealthOut(
            source="github",
            state="fresh",
            last_success_at=now,
            last_attempt_at=now,
            last_error_type=None,
            age_hours=0.5,
        ),
        SourceHealthOut(
            source="jira",
            state="unavailable",
            last_success_at=None,
            last_attempt_at=now,
            last_error_type="AUTH_FAILED",
            age_hours=None,
        ),
    ]
    out = GetSourceHealthOutput(sources=health_items)
    dumped = out.model_dump()
    loaded = GetSourceHealthOutput.model_validate(dumped)
    assert len(loaded.sources) == 2
    assert loaded.sources[0].state == "fresh"
    assert loaded.sources[1].state == "unavailable"


def test_evidence_item_contract() -> None:
    """Verify EvidenceItem matches DATA_AND_EVIDENCE.md 6.5 specification."""
    now = datetime.now(UTC)
    evidence = EvidenceItem(
        id="ev_1",
        source="jira",
        entity_type="work_item",
        entity_key="AUTH-245",
        source_url="https://example.atlassian.net/browse/AUTH-245",
        summary="AUTH-245 'Refresh token rotation' assigned to Keshan",
        excerpt="Capped summary text",
        observed_at=now,
        retrieved_at=now,
        source_state="fresh",
    )
    dumped = evidence.model_dump()
    loaded = EvidenceItem.model_validate(dumped)
    assert loaded.id == "ev_1"
    assert loaded.source_state == "fresh"


def test_claim_evidence_ids_invariance() -> None:
    """Verify Claim strictly requires string evidence IDs and rejects embedded objects."""
    claim = Claim(
        text="Keshan is actively working on AUTH-245",
        classification="fact",
        evidence_ids=["ev_1", "ev_2"],
    )
    assert claim.claim == "Keshan is actively working on AUTH-245"
    assert claim.evidence_ids == ["ev_1", "ev_2"]

    # Reject embedded dict or object in evidence_ids per DEC-004
    with pytest.raises(ValidationError):
        Claim(
            text="Invalid claim",
            classification="fact",
            evidence_ids=[{"id": "ev_1"}],  # type: ignore[list-item]
        )

    with pytest.raises(ValidationError):
        Claim(
            text="Invalid classification",
            classification="invalid_class",  # type: ignore[arg-type]
            evidence_ids=["ev_1"],
        )


def test_insight_and_member_insight_roundtrip() -> None:
    """Verify Insight and MemberInsight full response contracts."""
    now = datetime.now(UTC)
    evidence = EvidenceItem(
        id="ev_1",
        source="github",
        entity_type="pull_request",
        entity_key="acme/api#182",
        source_url="https://github.com/acme/api/pull/182",
        summary="PR #182 opened by Keshan",
        excerpt=None,
        observed_at=now,
        retrieved_at=now,
        source_state="fresh",
    )
    insight = Insight(
        claim="PR 182 is approved and awaiting merge",
        classification="fact",
        confidence="HIGH",
        evidence=[evidence],
        conflicts=[],
    )
    assert insight.text == "PR 182 is approved and awaiting merge"

    member_insight = MemberInsight(
        user_id=7,
        likely_current_work=insight,
        assigned=[],
        blockers=[],
        risks=[insight],
        unknowns=[],
        last_synced={"github": now, "jira": now},
        source_health=[
            SourceHealthOut(
                source="github",
                state="fresh",
                last_success_at=now,
                last_attempt_at=now,
                last_error_type=None,
                age_hours=1.2,
            )
        ],
        summary="Keshan is on track.",
    )
    dumped = member_insight.model_dump()
    loaded = MemberInsight.model_validate(dumped)
    assert loaded.user_id == 7
    assert loaded.likely_current_work is not None
    assert loaded.likely_current_work.confidence == "HIGH"
    assert len(loaded.risks) == 1
    assert loaded.last_synced["github"] is not None
    assert len(loaded.source_health) == 1
