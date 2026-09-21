import re
from typing import Any, Dict, List
import logging

logger = logging.getLogger(__name__)

# Forbidden person-judgment terms as per AI_BEHAVIOR.md requirements
FORBIDDEN_TERMS = [
    "lazy", "incompetent", "stupid", "negligent", "careless", 
    "unprofessional", "failure", "useless", "bad"
]

def extract_ticket_keys_and_prs(text: str) -> List[str]:
    """Extracts ticket keys and PR numbers (e.g., PROJ-123, #45) from text."""
    patterns = r'\b[A-Z]+-\d+\b|#\d+'
    return list(set(re.findall(patterns, text)))

def validate_and_assemble_narrative(
    narrative_data: Dict[str, Any], 
    findings: List[str], 
    raw_findings_text: str,
    deterministic_fallback: Dict[str, Any],
    additional_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validates narrative output against invented entities, forbidden language, and shape constraints.
    Falls back to deterministic summary if any check fails.
    """
    summary = narrative_data.get("summary", "")
    dropped_claims = []

    # Check 1: Shape (Both fields non-empty and within bounds)
    if not summary or len(summary.strip()) < 20:
        logger.warning("Validation failed: Shape bounds or empty summary. Using fallback.")
        deterministic_fallback["dropped_claims"] = ["SHAPE_INVALID"]
        return assemble_response(deterministic_fallback, additional_context)

    # Check 2: Invented Entity (Ticket keys / PR numbers in summary must appear in findings)
    findings_combined = raw_findings_text + " " + " ".join(findings)
    valid_entities = set(extract_ticket_keys_and_prs(findings_combined))
    summary_entities = extract_ticket_keys_and_prs(summary)
    
    for entity in summary_entities:
        if entity not in valid_entities:
            logger.warning("Validation failed: Invented entity '%s' found. Using fallback.", entity)
            dropped_claims.append(f"INVENTED_ENTITY_{entity}")
            deterministic_fallback["dropped_claims"] = dropped_claims
            return assemble_response(deterministic_fallback, additional_context)

    # Check 3: Forbidden Language (Person-judgment terms)
    summary_lower = summary.lower()
    for term in FORBIDDEN_TERMS:
        if re.search(r'\b' + term + r'\b', summary_lower):
            logger.warning("Validation failed: Forbidden language term '%s' found. Using fallback.", term)
            dropped_claims.append(f"FORBIDDEN_LANGUAGE_{term}")
            deterministic_fallback["dropped_claims"] = dropped_claims
            return assemble_response(deterministic_fallback, additional_context)

    # Check 4: Assembly (Pass valid narrative through with metadata)
    return {
        "summary": summary,
        "eval_count": narrative_data.get("eval_count", 0),
        "prompt_eval_count": narrative_data.get("prompt_eval_count", 0),
        "wall_clock_latency": narrative_data.get("wall_clock_latency", 0.0),
        "fallback_used": False,
        "dropped_claims": [],
        "claims": additional_context.get("claims", []),
        "blockers": additional_context.get("blockers", []),
        "risks": additional_context.get("risks", []),
        "conflicts": additional_context.get("conflicts", []),
        "confidence": additional_context.get("confidence", {})
    }

def assemble_response(fallback_data: Dict[str, Any], additional_context: Dict[str, Any]) -> Dict[str, Any]:
    """Assembles final response using fallback narrative while keeping findings and context intact."""
    return {
        "summary": fallback_data.get("summary"),
        "eval_count": fallback_data.get("eval_count", 0),
        "prompt_eval_count": fallback_data.get("prompt_eval_count", 0),
        "wall_clock_latency": fallback_data.get("wall_clock_latency", 0.0),
        "fallback_used": True,
        "dropped_claims": fallback_data.get("dropped_claims", []),
        "claims": additional_context.get("claims", []),
        "blockers": additional_context.get("blockers", []),
        "risks": additional_context.get("risks", []),
        "conflicts": additional_context.get("conflicts", []),
        "confidence": additional_context.get("confidence", {})
    }