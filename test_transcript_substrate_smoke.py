"""
End-to-end smoke tests for the deterministic transcript substrate.

Exercises the full stack: agent handoff → ledger → topology → diff → audit.
No real model calls, no schema changes, no ledger semantic changes.
"""
import json
import os
import tempfile

from ledger_writer import LedgerWriter, verify_ledger
from replay_audit import compute_replay_audit
from transcript_diff import diff_transcript_events
from transcript_event import make_transcript_event, canonical_json
from transcript_ledger import (
    append_transcript_event,
    replay_execution_events,
    replay_transcript_events,
    verify_mixed_ledger,
)
from transcript_llm_agent import fake_model, run_agent_turn, run_two_agent_handoff
from transcript_topology import compute_transcript_linearization

RUN_ID = "run_smoke_001"
TS_A = "2026-05-13T10:00:00+00:00"
TS_B = "2026-05-13T10:00:01+00:00"
TS_C = "2026-05-13T10:00:02+00:00"


def _fresh():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.unlink(path)
    return path


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# 1. Two-agent handoff produces two valid transcript events in ledger
def test_handoff_produces_two_events():
    result = run_two_agent_handoff(_fresh())
    assert result["chain_ok"] is True
    assert len(result["replay_order"]) == 2
    assert result["event_a"]["event_type"] == "transcript.message"
    assert result["event_b"]["event_type"] == "transcript.message"
    assert result["event_a"]["role"] == "proposal"
    assert result["event_b"]["role"] == "critique"


# 2. Ledger hash-chain passes verification after handoff
def test_ledger_chain_valid_after_handoff():
    path = _fresh()
    run_two_agent_handoff(path)
    v = verify_mixed_ledger(path)
    assert v["ok"] is True
    assert v["count"] == 2
    assert v["failures"] == []


# 3. Mixed ledger: execution events and transcript events replay independently
def test_mixed_ledger_replay_independent():
    path = _fresh()
    writer = LedgerWriter(path)
    writer.append({"type": "execution.event", "payload": {"step": 1}})
    writer.append({"type": "execution.event", "payload": {"step": 2}})
    run_two_agent_handoff(path)
    writer2 = LedgerWriter(path)
    writer2.append({"type": "execution.event", "payload": {"step": 3}})

    exec_events = replay_execution_events(path)
    transcript_events = replay_transcript_events(path)

    assert len(exec_events) == 3
    assert len(transcript_events) == 2
    assert all(e["event_type"] == "transcript.message" for e in transcript_events)
    assert all(e.get("event_type") != "transcript.message" for e in exec_events)


# 4. Topology linearization is deterministic and parent-ordered
def test_topology_linearization_parent_ordered():
    path = _fresh()
    result = run_two_agent_handoff(path)
    events = replay_transcript_events(path)
    lin = compute_transcript_linearization(events)

    assert lin["node_count"] == 2
    assert lin["orphaned"] == []
    id_a = result["event_a"]["message_id"]
    id_b = result["event_b"]["message_id"]
    assert lin["order"].index(id_a) < lin["order"].index(id_b)


# 5. Topology hash is stable across repeated linearizations
def test_topology_hash_stable():
    path = _fresh()
    run_two_agent_handoff(path)
    events = replay_transcript_events(path)
    hashes = {compute_transcript_linearization(events)["topology_hash"] for _ in range(5)}
    assert len(hashes) == 1


# 6. Diff between empty and populated transcript detects all events as added
def test_diff_detects_added_events():
    path = _fresh()
    run_two_agent_handoff(path)
    events = replay_transcript_events(path)
    diff = diff_transcript_events([], events)
    assert len(diff["added"]) == 2
    assert diff["removed"] == []
    assert diff["unchanged"] == []
    assert diff["diff_id"].startswith("tdiff_")


# 7. Diff between identical states is empty
def test_diff_identical_states_empty():
    path = _fresh()
    run_two_agent_handoff(path)
    events = replay_transcript_events(path)
    diff = diff_transcript_events(events, events)
    assert diff["added"] == []
    assert diff["removed"] == []
    assert len(diff["unchanged"]) == 2


# 8. Replay audit hashes are stable and artifact_hash changes when events change
def test_replay_audit_stable_and_sensitive():
    path = _fresh()
    run_two_agent_handoff(path)
    events = replay_transcript_events(path)

    audits = [_canon(compute_replay_audit(events)) for _ in range(5)]
    assert len(set(audits)) == 1

    # Adding a third event changes the audit
    proposal = events[0]
    reply = make_transcript_event(
        run_id=RUN_ID, sender="agent_c", recipient="broadcast",
        role="reply", content="Additional reply event",
        created_at=TS_C,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    audit_3 = compute_replay_audit(events + [reply])
    assert audit_3["artifact_hash"] != compute_replay_audit(events)["artifact_hash"]


# 9. fake_model is deterministic: same input → same output, different input → different output
def test_fake_model_deterministic_and_sensitive():
    msg = make_transcript_event(
        run_id=RUN_ID, sender="agent_a", recipient="broadcast",
        role="proposal", content="stress causes fatigue",
        created_at=TS_A,
    )
    out1 = [fake_model([msg]) for _ in range(5)]
    assert len(set(out1)) == 1

    msg2 = make_transcript_event(
        run_id=RUN_ID, sender="agent_a", recipient="broadcast",
        role="proposal", content="completely different content",
        created_at=TS_B,
    )
    assert fake_model([msg]) != fake_model([msg2])
    assert fake_model([msg]) != fake_model([])


# 10. Full substrate round-trip is byte-identical across repeated runs
def test_full_round_trip_byte_identical():
    def _run():
        result = run_two_agent_handoff(_fresh())
        events = [result["event_a"], result["event_b"]]
        lin = compute_transcript_linearization(events)
        audit = compute_replay_audit(events)
        diff = diff_transcript_events([], events)
        return _canon({
            "replay_order": result["replay_order"],
            "topology_hash": lin["topology_hash"],
            "artifact_hash": audit["artifact_hash"],
            "diff_id": diff["diff_id"],
        })

    results = {_run() for _ in range(3)}
    assert len(results) == 1
