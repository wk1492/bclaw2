import pytest

from epistemic_event import (
    EPISTEMIC_FIELDS,
    VALID_CLAIM_TYPES,
    VALID_EPISTEMIC_STATUSES,
    epistemic_claim_id,
    make_epistemic_event,
    strip_epistemic_fields,
)
from transcript_event import canonical_json, make_transcript_event
from transcript_ledger import append_transcript_event
from transcript_validator import validate_transcript_event

RUN_ID = "run_epistemic_test"
TS = "2026-05-14T10:00:00+00:00"


def _plain():
    return make_transcript_event(RUN_ID, "agent_a", "broadcast", "proposal",
                                 "Plain content", TS)


def _full():
    return make_epistemic_event(
        RUN_ID, "agent_a", "broadcast", "proposal", "Epistemic content", TS,
        claim_type="assertion",
        evidence_refs=["tmsg_abc123"],
        confidence=0.85,
        epistemic_status="proposed",
    )


# 1. Plain transcript event round-trips through strip_epistemic_fields unchanged
def test_strip_plain_event_unchanged():
    event = _plain()
    stripped = strip_epistemic_fields(event)
    assert stripped == event


# 2. strip_epistemic_fields does not mutate input
def test_strip_does_not_mutate_input():
    event = _full()
    original_keys = set(event.keys())
    strip_epistemic_fields(event)
    assert set(event.keys()) == original_keys


# 3. make_epistemic_event with no epistemic kwargs produces valid transcript.message event
def test_no_epistemic_kwargs_produces_valid_event():
    event = make_epistemic_event(RUN_ID, "agent_a", "broadcast", "proposal",
                                  "Content", TS)
    assert event["event_type"] == "transcript.message"
    assert EPISTEMIC_FIELDS.isdisjoint(event.keys())
    validate_transcript_event(event)


# 4. make_epistemic_event with all epistemic kwargs includes those fields
def test_all_epistemic_kwargs_present():
    event = _full()
    assert event["claim_type"] == "assertion"
    assert event["evidence_refs"] == ["tmsg_abc123"]
    assert event["confidence"] == 0.85
    assert event["epistemic_status"] == "proposed"


# 5. Invalid claim_type raises ValueError
def test_invalid_claim_type_raises():
    with pytest.raises(ValueError, match="claim_type"):
        make_epistemic_event(RUN_ID, "a", "b", "proposal", "c", TS,
                             claim_type="belief")


# 6. Invalid epistemic_status raises ValueError
def test_invalid_epistemic_status_raises():
    with pytest.raises(ValueError, match="epistemic_status"):
        make_epistemic_event(RUN_ID, "a", "b", "proposal", "c", TS,
                             epistemic_status="unknown")


# 7. confidence out of range raises ValueError
def test_confidence_out_of_range_raises():
    with pytest.raises(ValueError, match="confidence"):
        make_epistemic_event(RUN_ID, "a", "b", "proposal", "c", TS,
                             confidence=1.5)
    with pytest.raises(ValueError, match="confidence"):
        make_epistemic_event(RUN_ID, "a", "b", "proposal", "c", TS,
                             confidence=-0.1)


# 8. evidence_refs not a list raises ValueError
def test_evidence_refs_not_list_raises():
    with pytest.raises(ValueError, match="evidence_refs"):
        make_epistemic_event(RUN_ID, "a", "b", "proposal", "c", TS,
                             evidence_refs="tmsg_abc123")


# 9. Canonical serialization of epistemic event is byte-identical across repeated calls
def test_canonical_serialization_byte_identical():
    event = _full()
    results = [canonical_json(event) for _ in range(8)]
    assert len(set(results)) == 1


# 10. epistemic_claim_id is stable across repeated calls
def test_epistemic_claim_id_stable():
    event = _full()
    ids = [epistemic_claim_id(event) for _ in range(5)]
    assert len(set(ids)) == 1
    assert ids[0].startswith("claim_")
    assert len(ids[0]) == 30  # "claim_" (6) + 24 hex chars


# 11. epistemic_claim_id changes when epistemic content changes
def test_epistemic_claim_id_changes_with_content():
    event_a = make_epistemic_event(RUN_ID, "a", "b", "proposal", "Content A", TS,
                                    claim_type="assertion")
    event_b = make_epistemic_event(RUN_ID, "a", "b", "proposal", "Content B", TS,
                                    claim_type="hypothesis")
    assert epistemic_claim_id(event_a) != epistemic_claim_id(event_b)


# 12. Epistemic event appends to ledger via existing append_transcript_event
def test_epistemic_event_appends_to_ledger(tmp_path):
    path = tmp_path / "ledger.jsonl"
    event = _full()
    result = append_transcript_event(event, path)
    assert result is not None
    assert path.exists()
    lines = [l for l in path.read_text().splitlines() if l.strip()]
    assert len(lines) == 1


# 13. Stripped event validates as a normal transcript.message event
def test_stripped_event_validates():
    event = _full()
    stripped = strip_epistemic_fields(event)
    validate_transcript_event(stripped)
    assert EPISTEMIC_FIELDS.isdisjoint(stripped.keys())


# Extra: all VALID_CLAIM_TYPES are accepted without error
def test_all_valid_claim_types_accepted():
    for ct in VALID_CLAIM_TYPES:
        e = make_epistemic_event(RUN_ID, "a", "b", "proposal", "c", TS,
                                  claim_type=ct)
        assert e["claim_type"] == ct


# Extra: all VALID_EPISTEMIC_STATUSES are accepted without error
def test_all_valid_epistemic_statuses_accepted():
    for status in VALID_EPISTEMIC_STATUSES:
        e = make_epistemic_event(RUN_ID, "a", "b", "proposal", "c", TS,
                                  epistemic_status=status)
        assert e["epistemic_status"] == status


# Extra: confidence boundary values 0.0 and 1.0 are accepted
def test_confidence_boundary_values_accepted():
    for val in (0.0, 1.0, 0.5):
        e = make_epistemic_event(RUN_ID, "a", "b", "proposal", "c", TS,
                                  confidence=val)
        assert e["confidence"] == val


# Extra: int confidence raises ValueError (must be float)
def test_confidence_int_raises():
    with pytest.raises(ValueError, match="confidence"):
        make_epistemic_event(RUN_ID, "a", "b", "proposal", "c", TS,
                             confidence=1)
