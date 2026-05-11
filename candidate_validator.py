import json
from pathlib import Path

REQUIRED_KEYS = {"candidate_id", "id", "task_id", "action", "status"}

def validate_candidate(candidate: dict):
    if not isinstance(candidate, dict):
        raise ValueError("Candidate must be a dictionary")
    
    missing = [k for k in REQUIRED_KEYS if k not in candidate]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
    
    if not candidate.get("candidate_id"):
        raise ValueError("candidate_id cannot be empty")
    if not candidate.get("task_id"):
        raise ValueError("task_id cannot be empty")
    if not candidate.get("action"):
        raise ValueError("action cannot be empty")
    if candidate.get("status") not in {"proposed", "approved", "implemented", "archived"}:
        raise ValueError("status must be one of: proposed, approved, implemented, archived")
    
    # Allow manual underperformance candidates
    if candidate.get("task_id") == "underperformance_v1":
        if not candidate.get("source_model"):
            raise ValueError("source_model required for underperformance_v1")

_QUALITY_FIELDS = ("proposed_action", "rationale", "evidence", "risk_notes")


def score_candidate(candidate: dict) -> float:
    score = sum(25.0 for f in _QUALITY_FIELDS if candidate.get(f))
    if candidate.get("source_model") == "manual":
        score = max(0.0, score - 10.0)
    return score


def require_candidate_quality(candidate: dict, threshold: float = 75.0) -> float:
    score = score_candidate(candidate)
    if score < threshold:
        raise ValueError(f"Candidate quality {score} below threshold {threshold}")
    return score


if __name__ == "__main__":
    print("PASS: candidate_validator loaded")
    # Quick self-test
    test_c = {
        "candidate_id": "test-001",
        "id": "test-001",
        "task_id": "underperformance_v1",
        "action": "Test manual underperformance",
        "proposed_action": "Test manual underperformance",
        "rationale": "Testing",
        "status": "proposed",
        "source_model": "manual"
    }
    validate_candidate(test_c)
    print("PASS: manual underperformance candidate accepted")
