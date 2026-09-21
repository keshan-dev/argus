"""ARGUS agent package.

Contains the deterministic findings engine (conflicts, blockers, risks, confidence,
and deterministic member summaries) under DEC-018 and DEC-019.
"""

from app.agent.blockers import BlockerFinding, detect_blockers
from app.agent.confidence import ConfidenceLevel, evaluate_confidence
from app.agent.conflicts import ConflictFinding, detect_conflicts
from app.agent.deterministic_summary import (
    FALLBACK_HEADER,
    PRODUCTIVITY_CONTEXT_NOTE,
    DeterministicSummaryResult,
    generate_deterministic_summary,
)
from app.agent.risks import RiskFinding, detect_risks

__all__ = [
    "BlockerFinding",
    "detect_blockers",
    "ConfidenceLevel",
    "evaluate_confidence",
    "ConflictFinding",
    "detect_conflicts",
    "DeterministicSummaryResult",
    "generate_deterministic_summary",
    "PRODUCTIVITY_CONTEXT_NOTE",
    "FALLBACK_HEADER",
    "RiskFinding",
    "detect_risks",
]
