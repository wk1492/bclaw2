from candidate_validator import score_candidate, require_candidate_quality


def test_high_quality_candidate_scores_above_threshold():
    candidate = {
        "proposed_action": "Create a deterministic ledger analytics script that summarizes validation outcomes and failure patterns.",
        "rationale": "This improves system observability by turning raw ledger entries into actionable feedback for future improvement cycles.",
        "evidence": "The existing idea_ledger.jsonl already stores validation and failure records that can be counted and summarized.",
        "risk_notes": "Low risk because the first version can be read-only and avoid changing any system behavior.",
    }
    assert score_candidate(candidate) >= 75
    assert require_candidate_quality(candidate) >= 75


if __name__ == "__main__":
    test_high_quality_candidate_scores_above_threshold()
    print("PASS: candidate quality scoring works")
