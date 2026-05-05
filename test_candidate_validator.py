# BCLAW2 Candidate Validator Tests
from candidate_validator import validate_candidate

VALID_CANDIDATE = {
    "id": "cand_001",
    "source_model": "claude-sonnet",
    "task_id": "task_42",
    "proposed_action": "add field X to schema",
    "rationale": "needed for evaluation layer",
    "evidence": "evaluation_input shows gap",
    "risk_notes": "none identified",
    "status": "proposed",
}

def test_candidate_missing_field_raises():
    candidate = {k: v for k, v in VALID_CANDIDATE.items() if k != "status"}
    try:
        validate_candidate(candidate)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "status" in str(e)

if __name__ == "__main__":
    test_candidate_missing_field_raises()
    print("PASS: candidate validator rejects missing required field")
