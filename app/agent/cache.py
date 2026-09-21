import hashlib
import json
from typing import Any, Dict, List

def compute_evidence_hash(subject_user_id: str, question_type: str, evidence_set: List[Dict[str, Any]]) -> str:
    """
    Computes a stable SHA-256 cache key hash from subject_user_id, 
    question_type, and a deterministically sorted evidence set.
    """
    # Ensure keys are sorted deterministically to prevent hash mismatches
    serialized_evidence = json.dumps(evidence_set, sort_keys=True, default=str)
    raw_key_material = f"{subject_user_id}:{question_type}:{serialized_evidence}"
    return hashlib.sha256(raw_key_material.encode("utf-8")).hexdigest()