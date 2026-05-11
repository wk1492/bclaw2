"""
Phase 3/4 deterministic transcript replay proof.

Three-message exchange: proposal -> critique -> arbiter reply.
All assertions are byte-stable and deterministic across repeated runs.
"""
import json
import pytest
from pathlib import Path

from transcript_event import make_transcript_event, canonical_json
from transcript_ledger import (
    append_transcript_event,
    replay_transcript_events,
    replay_execution_events,
    verify_mixed_ledger,
)
from ledger_writer import LedgerWriter

RUN_ID = "run_replay_proof_001"
TS_A = "2026-05-10T11:00:00+00:00"
TS_B = "2026-05-10T11:00:01+00:00"
TS_C = "2026-05-10T11:00:02+00:00"


def _make_exchange():
    proposal = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_a",
        recipient="agent_b",
        role="proposal",
        content="Add causal edge: fatigue -> error_rate",
        created_at=TS_A,
    )
    critique = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_b",
        recipient="agent_a",
        role="critique",
        content="Edge weight unsubstantiated; evidence threshold not met",
        created_at=TS_B,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    arbiter = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_arbiter",
        recipient="broadcast",
        role="arbiter",
        content="Proposal deferred pending evidence. Critique accepted.",
        created_at=TS_C,
        parent_message_id=critique["message_id"],
        references=[critique["message_id"], proposal["message_id"]],
    )
    return proposal, critique, arbiter


def _append_exchange(path):
    proposal, critique, arbiter = _make_exchange()
    append_transcript_event(proposal, path)
    append_transcript_event(critique, path)
    append_transcript_event(arbiter, path)
    return proposal, critique, arbiter


# 1. End-to-end append + replay + reconstruction
def test_end_to_end_append_replay_reconstruct(tmp_path):
    path = tmp_path / "ledger.jsonl"
    proposal, critique, arbiter = _append_exchange(path)

    thread = replay_transcript_events(path)

    assert len(thread) == 3
    assert thread[0]["message_id"] == proposal["message_id"]
    assert thread[1]["message_id"] == critique["message_id"]
    assert thread[2]["message_id"] == arbiter["message_id"]

    assert thread[0]["role"] == "proposal"
    assert thread[1]["role"] == "critique"
    assert thread[2]["role"] == "arbiter"

    assert thread[1]["parent_message_id"] == proposal["message_id"]
    assert thread[2]["parent_message_id"] == critique["message_id"]


# 2. Byte-stable output across repeated runs
def test_replay_output_is_byte_stable(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _append_exchange(path)

    def serialized():
        thread = replay_transcript_events(path)
        return json.dumps(thread, sort_keys=True, separators=(",", ":"))

    run1 = serialized()
    run2 = serialized()
    run3 = serialized()
    assert run1 == run2 == run3


# 3. Mixed ledger: execution replay unchanged
def test_mixed_ledger_execution_replay_unchanged(tmp_path):
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    e1 = writer.append({"type": "execution.event", "payload": {"step": 1}})
    e2 = writer.append({"type": "execution.event", "payload": {"step": 2}})

    exec_before = replay_execution_events(path)

    _append_exchange(path)

    writer2 = LedgerWriter(path)
    e3 = writer2.append({"type": "execution.event", "payload": {"step": 3}})

    exec_after = replay_execution_events(path)

    assert len(exec_after) == 3
    assert exec_after[0]["payload"] == {"step": 1}
    assert exec_after[1]["payload"] == {"step": 2}
    assert exec_after[2]["payload"] == {"step": 3}

    for before, after in zip(exec_before, exec_after[:2]):
        assert before["event_hash"] == after["event_hash"]


# 4. Transcript reconstruction ignores execution events
def test_transcript_reconstruction_ignores_execution_events(tmp_path):
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    writer.append({"type": "execution.event", "payload": {"x": 99}})

    _append_exchange(path)

    writer2 = LedgerWriter(path)
    writer2.append({"type": "execution.event", "payload": {"x": 100}})

    thread = replay_transcript_events(path)
    assert len(thread) == 3
    for event in thread:
        assert event.get("event_type") == "transcript.message"
        assert event.get("type") != "execution.event"


# 5. Stable parent/child ordering
def test_parent_child_ordering_stable(tmp_path):
    path = tmp_path / "ledger.jsonl"
    proposal, critique, arbiter = _append_exchange(path)

    thread = replay_transcript_events(path)

    ids = [e["message_id"] for e in thread]
    assert ids == [proposal["message_id"], critique["message_id"], arbiter["message_id"]]

    assert thread[1]["parent_message_id"] == ids[0]
    assert thread[2]["parent_message_id"] == ids[1]
    assert ids[0] in thread[2]["references"]
    assert ids[1] in thread[2]["references"]


# 6. Hash-chain integrity valid after full three-message exchange
def test_hash_chain_integrity_after_three_message_exchange(tmp_path):
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    writer.append({"type": "execution.event", "payload": {"step": 1}})

    _append_exchange(path)

    writer2 = LedgerWriter(path)
    writer2.append({"type": "execution.event", "payload": {"step": 2}})

    result = verify_mixed_ledger(path)
    assert result["ok"] is True
    assert result["count"] == 5
    assert result["failures"] == []


# 7. Canonical serialization of replayed thread is deterministic
def test_replayed_thread_canonical_json_deterministic(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _append_exchange(path)

    thread = replay_transcript_events(path)
    s1 = json.dumps(thread, sort_keys=True, separators=(",", ":"))
    s2 = json.dumps(list(reversed(thread)), sort_keys=True, separators=(",", ":"))

    # Order matters: replay order is deterministic, not reversible
    assert s1 != s2

    # But two replays from same ledger are identical
    thread2 = replay_transcript_events(path)
    assert json.dumps(thread2, sort_keys=True, separators=(",", ":")) == s1


# 8. message_ids are stable (content-addressed, not random)
def test_message_ids_are_content_addressed(tmp_path):
    proposal1, critique1, arbiter1 = _make_exchange()
    proposal2, critique2, arbiter2 = _make_exchange()

    assert proposal1["message_id"] == proposal2["message_id"]
    assert critique1["message_id"] == critique2["message_id"]
    assert arbiter1["message_id"] == arbiter2["message_id"]
