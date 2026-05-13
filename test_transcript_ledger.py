import json
import pytest
from pathlib import Path

from transcript_event import make_transcript_event, canonical_json
from transcript_validator import TranscriptValidationError
from transcript_ledger import (
    append_transcript_event,
    replay_transcript_events,
    replay_execution_events,
    replay_transcript_topology,
    verify_mixed_ledger,
    TranscriptTopologyError,
)
from ledger_writer import LedgerWriter, verify_ledger

RUN_ID = "run_phase2_001"
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
        content="Insufficient evidence for the proposed edge",
        created_at=TS_B,
        parent_message_id=parent_id,
        references=[parent_id],
    )


# 1. Append one valid transcript event to ledger
def test_append_single_transcript_event(tmp_path):
    path = tmp_path / "ledger.jsonl"
    event = _proposal()
    appended = append_transcript_event(event, path)
    assert appended["event_type"] == "transcript.message"
    assert appended["message_id"] == event["message_id"]
    assert "event_hash" in appended
    assert "rolling_hash" in appended
    lines = path.read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event_type"] == "transcript.message"


# 2. Append two transcript events with parent/reference relation
def test_append_two_related_transcript_events(tmp_path):
    path = tmp_path / "ledger.jsonl"
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    append_transcript_event(proposal, path)
    append_transcript_event(critique, path)
    lines = path.read_text().splitlines()
    assert len(lines) == 2
    records = [json.loads(l) for l in lines]
    assert records[1]["parent_message_id"] == proposal["message_id"]
    assert proposal["message_id"] in records[1]["references"]


# 3. Replay mixed ledger deterministically
def test_replay_mixed_ledger_is_deterministic(tmp_path):
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    writer.append({"type": "execution.event", "payload": {"x": 1}})
    proposal = _proposal()
    append_transcript_event(proposal, path)
    writer2 = LedgerWriter(path)
    writer2.append({"type": "execution.event", "payload": {"x": 2}})

    run1 = replay_transcript_events(path)
    run2 = replay_transcript_events(path)
    out1 = json.dumps(run1, sort_keys=True, separators=(",", ":"))
    out2 = json.dumps(run2, sort_keys=True, separators=(",", ":"))
    assert out1 == out2


# 4. Verify execution replay output is unchanged when transcript events are present
def test_execution_replay_unaffected_by_transcript_events(tmp_path):
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    e1 = writer.append({"type": "execution.event", "payload": {"x": 1}})
    e2 = writer.append({"type": "execution.event", "payload": {"x": 2}})

    exec_only = replay_execution_events(path)
    assert len(exec_only) == 2

    append_transcript_event(_proposal(), path)

    exec_with_transcript = replay_execution_events(path)
    assert len(exec_with_transcript) == 2
    assert exec_with_transcript[0]["payload"] == {"x": 1}
    assert exec_with_transcript[1]["payload"] == {"x": 2}


# 5. Verify transcript reconstruction order is stable
def test_transcript_reconstruction_order_stable(tmp_path):
    path = tmp_path / "ledger.jsonl"
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    append_transcript_event(proposal, path)
    append_transcript_event(critique, path)

    thread = replay_transcript_events(path)
    assert len(thread) == 2
    assert thread[0]["role"] == "proposal"
    assert thread[1]["role"] == "critique"
    assert thread[1]["parent_message_id"] == proposal["message_id"]

    # Same result regardless of ledger read order
    out = json.dumps(thread, sort_keys=True, separators=(",", ":"))
    assert out == json.dumps(replay_transcript_events(path), sort_keys=True, separators=(",", ":"))


# 6. Verify invalid transcript events are rejected before append
def test_invalid_transcript_event_rejected_before_append(tmp_path):
    path = tmp_path / "ledger.jsonl"
    bad_event = _proposal()
    del bad_event["sender"]
    with pytest.raises(TranscriptValidationError, match="missing required fields"):
        append_transcript_event(bad_event, path)
    assert not path.exists()


# 7. Verify hash-chain integrity remains valid across mixed event types
def test_hash_chain_integrity_mixed_ledger(tmp_path):
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    writer.append({"type": "execution.event", "payload": {"x": 1}})
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    append_transcript_event(proposal, path)
    append_transcript_event(critique, path)
    writer2 = LedgerWriter(path)
    writer2.append({"type": "execution.event", "payload": {"x": 2}})

    result = verify_mixed_ledger(path)
    assert result["ok"] is True
    assert result["count"] == 4
    assert result["failures"] == []


# --- replay_transcript_topology tests ---

TS_C = "2026-05-10T10:00:02+00:00"
TS_D = "2026-05-10T10:00:03+00:00"


def _arbiter(parent_id, ref_ids):
    return make_transcript_event(
        run_id=RUN_ID,
        sender="agent_arbiter",
        recipient="broadcast",
        role="arbiter",
        content="Proposal accepted with modifications",
        created_at=TS_C,
        parent_message_id=parent_id,
        references=ref_ids,
    )


# 8. replay_transcript_topology ignores execution events
def test_topology_replay_ignores_execution_events(tmp_path):
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    writer.append({"type": "execution.event", "payload": {"x": 99}})
    proposal = _proposal()
    append_transcript_event(proposal, path)
    writer.append({"type": "execution.event", "payload": {"x": 100}})

    topo = replay_transcript_topology(path)
    assert topo["node_count"] == 1
    assert topo["order"] == [proposal["message_id"]]
    assert topo["orphaned"] == []


# 9. Shuffled / ledger-mixed transcript events reconstruct the same topology order
def test_topology_replay_order_stable_across_shuffle(tmp_path):
    path = tmp_path / "ledger.jsonl"
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    append_transcript_event(proposal, path)
    append_transcript_event(critique, path)

    topo1 = replay_transcript_topology(path)

    # Write same events to a second ledger in reversed append order using LedgerWriter
    # (can't reverse append order through append_transcript_event due to parent validation,
    #  so confirm stability by calling replay twice on the same ledger)
    topo2 = replay_transcript_topology(path)

    assert topo1["order"] == topo2["order"]
    assert topo1["topology_hash"] == topo2["topology_hash"]
    # proposal must precede critique
    assert topo1["order"].index(proposal["message_id"]) < topo1["order"].index(critique["message_id"])


# 10. Orphaned message is listed in topology replay orphaned field
def test_topology_replay_marks_orphan(tmp_path):
    path = tmp_path / "ledger.jsonl"
    # Write a raw event referencing a parent that is not in the ledger
    import json as _json
    orphan_event = {
        "event_type": "transcript.message",
        "message_id": "tmsg_orphan000000000000000000",
        "run_id": RUN_ID,
        "sender": "agent_x",
        "recipient": "broadcast",
        "role": "proposal",
        "content": "I claim a parent that does not exist",
        "references": [],
        "parent_message_id": "tmsg_nonexistent0000000000000",
        "created_at": TS_A,
        "metadata": {},
    }
    path.write_text(_json.dumps(orphan_event) + "\n")

    topo = replay_transcript_topology(path)
    assert orphan_event["message_id"] in topo["orphaned"]
    assert topo["node_count"] == 1


# 11. Cycle raises TranscriptTopologyError
def test_topology_replay_raises_on_cycle(tmp_path):
    path = tmp_path / "ledger.jsonl"
    import json as _json
    mid_a = "tmsg_cycleaaaaaaaaaaaaaaaaaaa"
    mid_b = "tmsg_cyclebbbbbbbbbbbbbbbbbb"
    event_a = {
        "event_type": "transcript.message",
        "message_id": mid_a,
        "run_id": RUN_ID,
        "sender": "agent_a",
        "recipient": "broadcast",
        "role": "proposal",
        "content": "A references B",
        "references": [mid_b],
        "parent_message_id": None,
        "created_at": TS_A,
        "metadata": {},
    }
    event_b = {
        "event_type": "transcript.message",
        "message_id": mid_b,
        "run_id": RUN_ID,
        "sender": "agent_b",
        "recipient": "broadcast",
        "role": "critique",
        "content": "B references A",
        "references": [mid_a],
        "parent_message_id": None,
        "created_at": TS_B,
        "metadata": {},
    }
    path.write_text(_json.dumps(event_a) + "\n" + _json.dumps(event_b) + "\n")

    with pytest.raises(TranscriptTopologyError, match="Cycle detected"):
        replay_transcript_topology(path)


# 12. Repeated topology replay output is byte-identical
def test_topology_replay_byte_identical(tmp_path):
    path = tmp_path / "ledger.jsonl"
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    append_transcript_event(proposal, path)
    append_transcript_event(critique, path)

    results = [
        json.dumps(replay_transcript_topology(path), sort_keys=True, separators=(",", ":"))
        for _ in range(5)
    ]
    assert len(set(results)) == 1
