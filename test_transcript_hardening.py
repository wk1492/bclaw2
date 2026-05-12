"""
Ledger hardening: replay-from-zero proof, duplicate rejection,
missing parent rejection, reordered lineage rejection,
tampered payload rejection, canonical serialization lock.
"""
import json
import os
import tempfile

import pytest

from transcript_event import canonical_json, make_transcript_event, message_id_hash
from transcript_ledger import append_transcript_event, replay_transcript_events, verify_mixed_ledger
from transcript_validator import TranscriptValidationError

RUN_ID = "hardening_run_001"
TS_A = "2026-05-12T10:00:00+00:00"
TS_B = "2026-05-12T10:00:01+00:00"
TS_C = "2026-05-12T10:00:02+00:00"


def _fresh():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.unlink(path)
    return path


def _proposal():
    return make_transcript_event(
        run_id=RUN_ID, sender="agent_a", recipient="broadcast",
        role="proposal", content="pace overextension detected",
        created_at=TS_A,
    )


def _critique(parent_id):
    return make_transcript_event(
        run_id=RUN_ID, sender="agent_b", recipient="broadcast",
        role="critique", content="insufficient evidence",
        created_at=TS_B,
        parent_message_id=parent_id,
        references=[parent_id],
    )


def _reply(parent_id):
    return make_transcript_event(
        run_id=RUN_ID, sender="agent_a", recipient="broadcast",
        role="reply", content="acknowledged",
        created_at=TS_C,
        parent_message_id=parent_id,
        references=[parent_id],
    )


def _serial(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


# 1. replay-from-zero proof
def test_replay_from_zero_proof():
    path = _fresh()
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    reply = _reply(critique["message_id"])
    append_transcript_event(proposal, path)
    append_transcript_event(critique, path)
    append_transcript_event(reply, path)

    run1 = _serial(replay_transcript_events(path))
    run2 = _serial(replay_transcript_events(path))
    run3 = _serial(replay_transcript_events(path))
    assert run1 == run2 == run3

    thread = replay_transcript_events(path)
    assert len(thread) == 3
    assert thread[0]["message_id"] == proposal["message_id"]
    assert thread[1]["message_id"] == critique["message_id"]
    assert thread[2]["message_id"] == reply["message_id"]


# 2. duplicate event rejection
def test_duplicate_event_rejected():
    path = _fresh()
    proposal = _proposal()
    append_transcript_event(proposal, path)
    with pytest.raises(TranscriptValidationError, match="duplicate"):
        append_transcript_event(proposal, path)


# 3. missing parent rejection
def test_missing_parent_rejected():
    path = _fresh()
    fake_parent_id = "tmsg_" + "a" * 24
    event = make_transcript_event(
        run_id=RUN_ID, sender="agent_b", recipient="broadcast",
        role="critique", content="critique with nonexistent parent",
        created_at=TS_B,
        parent_message_id=fake_parent_id,
        references=[fake_parent_id],
    )
    with pytest.raises(TranscriptValidationError, match="parent_message_id"):
        append_transcript_event(event, path)
    assert not os.path.exists(path)


# 4. reordered lineage rejection (child appended before parent)
def test_reordered_lineage_rejected():
    path = _fresh()
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    with pytest.raises(TranscriptValidationError, match="parent_message_id"):
        append_transcript_event(critique, path)
    append_transcript_event(proposal, path)
    appended = append_transcript_event(critique, path)
    assert appended["parent_message_id"] == proposal["message_id"]


# 5. tampered payload rejection
def test_tampered_payload_rejected():
    path = _fresh()
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    append_transcript_event(proposal, path)
    append_transcript_event(critique, path)

    result = verify_mixed_ledger(path)
    assert result["ok"] is True

    raw = open(path).read()
    tampered = raw.replace("pace overextension detected", "pace overextension TAMPERED", 1)
    assert tampered != raw
    with open(path, "w") as f:
        f.write(tampered)

    result = verify_mixed_ledger(path)
    assert result["ok"] is False
    assert len(result["failures"]) > 0


# 6. canonical serialization lock
def test_canonical_serialization_lock():
    fixed_event = {
        "content": "pace overextension detected",
        "created_at": TS_A,
        "event_type": "transcript.message",
        "metadata": {},
        "parent_message_id": None,
        "recipient": "broadcast",
        "references": [],
        "role": "proposal",
        "run_id": RUN_ID,
        "sender": "agent_a",
    }
    canon = canonical_json(fixed_event)
    assert '": ' not in canon   # no space after colon
    assert '", ' not in canon   # no space after comma
    assert '"content":"pace overextension detected"' in canon
    assert '"run_id":"hardening_run_001"' in canon
    assert canonical_json(fixed_event) == canon
    assert canonical_json(dict(reversed(list(fixed_event.items())))) == canon

    mid = message_id_hash(fixed_event)
    assert mid.startswith("tmsg_")
    assert len(mid) == 5 + 24
    assert message_id_hash(fixed_event) == mid
