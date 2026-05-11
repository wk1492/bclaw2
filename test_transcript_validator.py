import json
import pytest
from transcript_event import make_transcript_event, canonical_json
from transcript_validator import validate_transcript_event, reconstruct_thread, TranscriptValidationError

RUN_ID = "run_test_001"
TS_A = "2026-05-10T10:00:00+00:00"
TS_B = "2026-05-10T10:00:01+00:00"


def _proposal():
    return make_transcript_event(
        run_id=RUN_ID,
        sender="agent_a",
        recipient="agent_b",
        role="proposal",
        content="Add causal edge: stress -> performance_drop",
        created_at=TS_A,
    )


def _critique(parent_id):
    return make_transcript_event(
        run_id=RUN_ID,
        sender="agent_b",
        recipient="agent_a",
        role="critique",
        content="Insufficient evidence for stress -> performance_drop",
        created_at=TS_B,
        parent_message_id=parent_id,
        references=[parent_id],
    )


def test_valid_proposal_passes():
    event = _proposal()
    validate_transcript_event(event)


def test_valid_critique_passes():
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    validate_transcript_event(critique)


def test_missing_required_field_raises():
    event = _proposal()
    del event["sender"]
    with pytest.raises(TranscriptValidationError, match="missing required fields"):
        validate_transcript_event(event)


def test_invalid_event_type_raises():
    event = _proposal()
    event["event_type"] = "execution.event"
    with pytest.raises(TranscriptValidationError, match="invalid event_type"):
        validate_transcript_event(event)


def test_invalid_role_raises():
    event = _proposal()
    event["role"] = "narrator"
    with pytest.raises(TranscriptValidationError, match="invalid role"):
        validate_transcript_event(event)


def test_references_must_be_list():
    event = _proposal()
    event["references"] = "not-a-list"
    with pytest.raises(TranscriptValidationError, match="references must be a list"):
        validate_transcript_event(event)


def test_metadata_must_be_dict():
    event = _proposal()
    event["metadata"] = ["not", "a", "dict"]
    with pytest.raises(TranscriptValidationError, match="metadata must be a dict"):
        validate_transcript_event(event)


def test_empty_sender_raises():
    event = _proposal()
    event["sender"] = ""
    with pytest.raises(TranscriptValidationError, match="sender must be a non-empty string"):
        validate_transcript_event(event)


def test_canonical_serialization_uses_compact_separators():
    event = _proposal()
    serialized = canonical_json(event)
    # Verify compact separators by comparing against reference with known separators
    reference = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert serialized == reference
    roundtripped = json.loads(serialized)
    assert roundtripped == event


def test_canonical_serialization_is_deterministic():
    event = _proposal()
    assert canonical_json(event) == canonical_json(event)
    assert canonical_json(event) == canonical_json(dict(reversed(list(event.items()))))


def test_message_id_is_stable():
    e1 = _proposal()
    e2 = _proposal()
    assert e1["message_id"] == e2["message_id"]


def test_reconstruct_thread_ordering():
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    validate_transcript_event(proposal)
    validate_transcript_event(critique)

    thread = reconstruct_thread([critique, proposal])
    assert thread[0]["message_id"] == proposal["message_id"]
    assert thread[1]["message_id"] == critique["message_id"]


def test_reconstruct_thread_byte_stable():
    proposal = _proposal()
    critique = _critique(proposal["message_id"])

    thread1 = reconstruct_thread([proposal, critique])
    thread2 = reconstruct_thread([critique, proposal])

    assert [e["message_id"] for e in thread1] == [e["message_id"] for e in thread2]

    out1 = json.dumps(thread1, sort_keys=True, separators=(",", ":"))
    out2 = json.dumps(thread2, sort_keys=True, separators=(",", ":"))
    assert out1 == out2


def test_acceptance_two_agent_exchange():
    proposal = _proposal()
    critique = _critique(proposal["message_id"])

    for event in (proposal, critique):
        validate_transcript_event(event)

    thread = reconstruct_thread([proposal, critique])
    assert len(thread) == 2
    assert thread[0]["role"] == "proposal"
    assert thread[1]["role"] == "critique"
    assert thread[1]["parent_message_id"] == proposal["message_id"]

    serialized = json.dumps(thread, sort_keys=True, separators=(",", ":"))
    assert json.loads(serialized) == thread
