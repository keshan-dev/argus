import pytest
from app.agent.cache import compute_evidence_hash

def test_hash_stability_and_ordering():
    evidence_a = [{"id": 1, "text": "evidence one"}, {"id": 2, "text": "evidence two"}]
    evidence_b = [{"text": "evidence one", "id": 1}, {"text": "evidence two", "id": 2}] # Different key ordering
    
    hash_a = compute_evidence_hash("user_123", "risk_analysis", evidence_a)
    hash_b = compute_evidence_hash("user_123", "risk_analysis", evidence_b)
    
    assert hash_a == hash_b, "Hash must be stable regardless of dictionary key ordering."

def test_cache_miss_on_changed_evidence():
    evidence_1 = [{"id": 1, "text": "evidence one"}]
    evidence_2 = [{"id": 1, "text": "evidence modified"}]
    
    hash_1 = compute_evidence_hash("user_123", "risk_analysis", evidence_1)
    hash_2 = compute_evidence_hash("user_123", "risk_analysis", evidence_2)
    
    assert hash_1 != hash_2, "Different evidence must produce a different cache hash."

def test_cache_miss_on_different_user_or_type():
    evidence = [{"id": 1, "text": "evidence one"}]
    
    hash_1 = compute_evidence_hash("user_123", "risk_analysis", evidence)
    hash_2 = compute_evidence_hash("user_999", "risk_analysis", evidence)
    hash_3 = compute_evidence_hash("user_123", "other_type", evidence)
    
    assert hash_1 != hash_2
    assert hash_1 != hash_3