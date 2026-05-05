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

def score_candidate(candidate):
    score = 0

    action = candidate.get("proposed_action", "")
    rationale = candidate.get("rationale", "")
    evidence = candidate.get("evidence", "")
    risk = candidate.get("risk_notes", "")

    if len(action.strip()) >= 60:
        score += 25
    if len(rationale.strip()) >= 80:
        score += 25
    if len(evidence.strip()) >= 80:
        score += 30
    if len(risk.strip()) >= 50:
        score += 20

    return score


def require_candidate_quality(candidate, minimum=75):
    score = score_candidate(candidate)
    if score < minimum:
        raise ValidationError(f"candidate quality score too low: {score} < {minimum}")
    return score
