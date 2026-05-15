"""
Manual transcript-to-claim experiment — BCLAW3 Phase 2A proof of concept.

Demonstrates stages 1–4 of the 7-stage architecture:
  1. Agent speaks naturally (free text + embedded bclaw block)
  2. Agents respond and challenge (critique block references proposal)
  3. Agents teach computation (block payload carries structured claim)
  4. Extractor converts blocks into schema artifacts

No ledger writes. No model calls. No FCM mutation.
All inputs are hand-crafted deterministic fixtures.
"""
from epistemic_extractor import (
    extract_blocks,
    extract_from_transcript,
    validate_block,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

_PROPOSAL_CONTENT = """\
The pace projections suggest an early speed advantage.

```bclaw
{
  "type": "claim",
  "payload": {
    "claim_type": "pace_projection",
    "assertion": "early_speed_advantage",
    "confidence": "medium",
    "basis": ["fractional_splits", "field_speed_figure"]
  }
}
```

Further analysis pending final field scratch report.
"""

_CRITIQUE_CONTENT = """\
Pace projection may be overstated — rail bias nullifies speed advantage.

```bclaw
{
  "type": "claim",
  "payload": {
    "claim_type": "pace_correction",
    "assertion": "rail_bias_cancels_speed_advantage",
    "confidence": "high",
    "basis": ["track_condition_report", "post_position_stats"]
  }
}
```

Recommend arbiter weighting toward pace_correction before final output.
"""

_ARBITER_CONTENT = """\
Considering both claims, pace_correction takes precedence given current track.

```bclaw
{
  "type": "resolution",
  "payload": {
    "selected": "pace_correction",
    "rejected": "pace_projection",
    "rationale": "track_condition_report_supersedes_splits"
  }
}
```
"""

_EVENTS = [
    {
        "message_id": "tmsg_exp_proposal_001",
        "role": "proposal",
        "sender": "agent_researcher",
        "content": _PROPOSAL_CONTENT,
    },
    {
        "message_id": "tmsg_exp_critique_001",
        "role": "critique",
        "sender": "agent_critic",
        "content": _CRITIQUE_CONTENT,
    },
    {
        "message_id": "tmsg_exp_arbiter_001",
        "role": "arbiter",
        "sender": "agent_arbiter",
        "content": _ARBITER_CONTENT,
    },
]


# ── Tests ─────────────────────────────────────────────────────────────────────

# 1. Each agent message yields exactly one extracted block
def test_each_event_yields_one_block():
    artifact = extract_from_transcript(_EVENTS)
    for r in artifact["results"]:
        assert len(r["blocks"]) == 1, (
            f"expected 1 block in {r['message_id']}, got {len(r['blocks'])}"
        )


# 2. All extracted blocks pass validation
def test_all_blocks_valid():
    artifact = extract_from_transcript(_EVENTS)
    for r in artifact["results"]:
        for v in r["validated"]:
            assert v["ok"] is True, f"invalid block in {r['message_id']}: {v['error']}"


# 3. Block types match the structured message roles
def test_block_types_match_message_intent():
    artifact = extract_from_transcript(_EVENTS)
    types = [r["blocks"][0]["type"] for r in artifact["results"]]
    assert types == ["claim", "claim", "resolution"]


# 4. Proposal block carries expected payload keys
def test_proposal_block_payload_keys():
    blocks = extract_blocks(_PROPOSAL_CONTENT)
    assert len(blocks) == 1
    payload = blocks[0]["payload"]
    for key in ("claim_type", "assertion", "confidence", "basis"):
        assert key in payload, f"missing payload key: {key}"


# 5. Critique block payload references track condition
def test_critique_block_basis_includes_track_condition():
    blocks = extract_blocks(_CRITIQUE_CONTENT)
    assert "track_condition_report" in blocks[0]["payload"]["basis"]


# 6. Resolution block identifies selected and rejected claim
def test_resolution_block_selects_and_rejects():
    blocks = extract_blocks(_ARBITER_CONTENT)
    payload = blocks[0]["payload"]
    assert payload["selected"] == "pace_correction"
    assert payload["rejected"] == "pace_projection"


# 7. block_count == 3 (one per event)
def test_total_block_count():
    artifact = extract_from_transcript(_EVENTS)
    assert artifact["block_count"] == 3


# 8. error_count == 0
def test_zero_errors():
    artifact = extract_from_transcript(_EVENTS)
    assert artifact["error_count"] == 0


# 9. Free prose around blocks does not appear in extracted payloads
def test_prose_excluded_from_payloads():
    artifact = extract_from_transcript(_EVENTS)
    for r in artifact["results"]:
        for block in r["blocks"]:
            raw = str(block)
            assert "pace projections suggest" not in raw
            assert "Further analysis" not in raw
            assert "Considering both claims" not in raw


# 10. artifact_id is deterministic across repeated extractions
def test_experiment_artifact_id_deterministic():
    id1 = extract_from_transcript(_EVENTS)["artifact_id"]
    id2 = extract_from_transcript(_EVENTS)["artifact_id"]
    assert id1 == id2


# 11. Changing one block payload changes artifact_id
def test_mutated_payload_changes_artifact_id():
    import copy
    original_id = extract_from_transcript(_EVENTS)["artifact_id"]
    mutated = copy.deepcopy(_EVENTS)
    mutated[0]["content"] = mutated[0]["content"].replace(
        '"confidence": "medium"', '"confidence": "high"'
    )
    mutated_id = extract_from_transcript(mutated)["artifact_id"]
    assert original_id != mutated_id


# 12. Result order matches event input order
def test_result_order_matches_event_order():
    artifact = extract_from_transcript(_EVENTS)
    expected_ids = [e["message_id"] for e in _EVENTS]
    actual_ids = [r["message_id"] for r in artifact["results"]]
    assert actual_ids == expected_ids
