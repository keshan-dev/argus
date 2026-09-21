import pytest
from app.agent.validation import validate_and_assemble_narrative

@pytest.fixture
def base_context():
    return {
        "claims": ["Claim 1"],
        "blockers": [],
        "risks": ["Risk 1"],
        "conflicts": [],
        "confidence": {"score": 0.9}
    }

@pytest.fixture
def fallback():
    return {"summary": "Deterministic fallback summary used.", "eval_count": 0, "wall_clock_latency": 0.1}

def test_validator_success(base_context, fallback):
    narrative = {"summary": "The system analyzed PROJ-123 successfully without errors."}
    findings = ["Finding regarding PROJ-123 fix."]
    raw_findings = "Finding regarding PROJ-123 fix."
    
    result = validate_and_assemble_narrative(narrative, findings, raw_findings, fallback, base_context)
    assert result["fallback_used"] is False
    assert result["summary"] == narrative["summary"]
    assert result["dropped_claims"] == []

def test_validator_invented_entity_rejection(base_context, fallback):
    narrative = {"summary": "The review on FAKE-999 shows critical issues."}
    findings = ["Finding regarding PROJ-123 fix."]
    raw_findings = "Finding regarding PROJ-123 fix."
    
    result = validate_and_assemble_narrative(narrative, findings, raw_findings, fallback, base_context)
    assert result["fallback_used"] is True
    assert "INVENTED_ENTITY_FAKE-999" in result["dropped_claims"]
    assert "Deterministic fallback" in result["summary"]

def test_validator_forbidden_language_rejection(base_context, fallback):
    narrative = {"summary": "The developer was extremely lazy and incompetent in writing PROJ-123."}
    findings = ["Finding regarding PROJ-123 fix."]
    raw_findings = "Finding regarding PROJ-123 fix."
    
    result = validate_and_assemble_narrative(narrative, findings, raw_findings, fallback, base_context)
    assert result["fallback_used"] is True
    assert any("FORBIDDEN_LANGUAGE" in claim for claim in result["dropped_claims"])