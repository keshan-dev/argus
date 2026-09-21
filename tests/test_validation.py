"""Unit tests for narrative validator stage S5 (P4-006, Issue #30)."""

from app.agent.validation import validate_narrative


def test_validator_success() -> None:
    """Valid narrative mentioning only allowed entities passes without rejection."""
    summary = (
        "The contributor is working on authentication token rotation under AUTH-245. "
        "Work is actively progressing on linked pull request #182."
    )
    needs_attention = "No blockers or critical risks require immediate attention."
    allowed = {"AUTH-245", "#182"}
    fallback = "Fallback summary text."

    result = validate_narrative(
        summary=summary,
        needs_attention=needs_attention,
        attention_needed=False,
        allowed_entities=allowed,
        fallback_text=fallback,
    )

    assert result.fallback_used is False
    assert result.summary == summary
    assert result.dropped_claims == []


def test_validator_invented_ticket_rejected() -> None:
    """Narrative citing a ticket not in findings is rejected and recorded."""
    summary = (
        "The contributor is currently implementing payment webhook processing under PAY-999. "
        "Work is ongoing on linked pull request #182."
    )
    needs_attention = "No blockers identified."
    allowed = {"AUTH-245", "#182"}  # PAY-999 is invented
    fallback = "Fallback summary text."

    result = validate_narrative(
        summary=summary,
        needs_attention=needs_attention,
        attention_needed=False,
        allowed_entities=allowed,
        fallback_text=fallback,
    )

    assert result.fallback_used is True
    assert result.summary == fallback
    assert any(
        c.get("reason") == "INVENTED_ENTITY" and c.get("entity") == "PAY-999"
        for c in result.dropped_claims
    )


def test_validator_invented_pr_rejected() -> None:
    """Narrative citing a PR number not in findings is rejected and recorded."""
    summary = (
        "Work on AUTH-245 is nearing completion in pull request #999. "
        "Automated regression checks are running."
    )
    needs_attention = "No blockers identified."
    allowed = {"AUTH-245", "#182"}  # #999 is invented
    fallback = "Fallback summary text."

    result = validate_narrative(
        summary=summary,
        needs_attention=needs_attention,
        attention_needed=False,
        allowed_entities=allowed,
        fallback_text=fallback,
    )

    assert result.fallback_used is True
    assert result.summary == fallback
    assert any(
        c.get("reason") == "INVENTED_ENTITY" and c.get("entity") == "#999"
        for c in result.dropped_claims
    )


def test_validator_forbidden_language_rejected() -> None:
    """Narrative containing person-judgment words is rejected and recorded."""
    summary = (
        "The engineer is extremely lazy and falling behind on AUTH-245 tasks. "
        "Development progress is slower than expected."
    )
    needs_attention = "The engineer is behind on deliverable dates."
    allowed = {"AUTH-245"}
    fallback = "Fallback summary text."

    result = validate_narrative(
        summary=summary,
        needs_attention=needs_attention,
        attention_needed=True,
        allowed_entities=allowed,
        fallback_text=fallback,
    )

    assert result.fallback_used is True
    assert result.summary == fallback
    assert any(c.get("reason") == "FORBIDDEN_LANGUAGE" for c in result.dropped_claims)


def test_validator_shape_invalid_rejected() -> None:
    """Empty or too-short narrative fails shape check and falls back."""
    result = validate_narrative(
        summary="Too short",
        needs_attention="",
        attention_needed=False,
        allowed_entities={"AUTH-245"},
        fallback_text="Fallback summary text.",
    )

    assert result.fallback_used is True
    assert result.summary == "Fallback summary text."
    assert any(c.get("reason") == "SHAPE_INVALID" for c in result.dropped_claims)
