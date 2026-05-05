# BCLAW2 Candidate Validator
REQUIRED_FIELDS = (
    "id", "source_model", "task_id", "proposed_action",
    "rationale", "evidence", "risk_notes", "status",
)

def validate_candidate(candidate: dict) -> None:
    """Raises ValueError if any required field is missing."""
    for field in REQUIRED_FIELDS:
        if field not in candidate:
            raise ValueError(f"candidate missing required field: '{field}'")
