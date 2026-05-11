# BCLAW2 Static Golden Agent Candidate Examples

EXAMPLE_AGENT_CANDIDATE_VALID = {
    "id": "cand_001",
    "source_model": "claude-sonnet",
    "task_id": "task_001",
    "proposed_action": "add conflict_ratio field to fusion output",
    "rationale": "conflict_ratio would surface proportional conflict signal for future evaluation policies",
    "evidence": "current conflict_count verified at 1 for single duplicate-id input in test_pipeline_return_summary",
    "risk_notes": "purely additive field; no existing fields modified; backward compatible",
    "status": "proposed",
    "candidate_id": "cand_001",
    "action": "evaluate",
}

EXAMPLE_AGENT_CANDIDATE_INVALID_MISSING_STATUS = {
    "id": "cand_002",
    "source_model": "gpt-4o",
    "task_id": "task_002",
    "proposed_action": "extend schema to support optional tags field",
    "rationale": "tags field would enable grouping of records for future policy use",
    "evidence": "schema_def.json currently has no optional field support",
    "risk_notes": "requires schema change; validator strict mode would reject tags unless schema updated",
    # "status" intentionally omitted
}
