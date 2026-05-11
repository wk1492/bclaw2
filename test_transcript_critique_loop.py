import json
import subprocess
import pytest
from pathlib import Path

from transcript_critique_loop import run_transcript_critique_loop
from transcript_ledger import replay_execution_events, replay_transcript_events, verify_mixed_ledger
from transcript_ledger import append_transcript_event
from transcript_topology import linearize_transcript_topology
from transcript_event import make_transcript_event
from ledger_writer import LedgerWriter


# 1. Exactly four transcript events emitted
def test_critique_loop_emits_four_events(tmp_path):
    path = tmp_path / "ledger.jsonl"
    summary = run_transcript_critique_loop(path)
    assert summary["event_count"] == 4


# 2. Topology: proposal root, critiques reference proposal, arbiter references critiques + proposal
def test_critique_loop_topology(tmp_path):
    path = tmp_path / "ledger.jsonl"
    summary = run_transcript_critique_loop(path)
    topo = summary["topology"]

    proposal_id = topo["proposal"]
    critique_ids = topo["critiques"]
    arbiter_id = topo["arbiter"]
    arbiter_refs = topo["arbiter_references"]

    assert len(critique_ids) == 2
    assert critique_ids[0] != critique_ids[1]

    # Critiques reference proposal
    from transcript_ledger import replay_transcript_events
    thread = replay_transcript_events(path)
    by_id = {e["message_id"]: e for e in thread}

    for cid in critique_ids:
        assert by_id[cid]["parent_message_id"] == proposal_id
        assert proposal_id in by_id[cid]["references"]

    # Arbiter references both critiques and proposal
    assert critique_ids[0] in arbiter_refs
    assert critique_ids[1] in arbiter_refs
    assert proposal_id in arbiter_refs


# 3. Deterministic replay order
def test_critique_loop_replay_order_deterministic(tmp_path):
    path1 = tmp_path / "l1.jsonl"
    path2 = tmp_path / "l2.jsonl"
    s1 = run_transcript_critique_loop(path1)
    s2 = run_transcript_critique_loop(path2)
    assert s1["replay_order"] == s2["replay_order"]


# 4. Deterministic reconstruction topology
def test_critique_loop_reconstruction_topology_deterministic(tmp_path):
    path1 = tmp_path / "l1.jsonl"
    path2 = tmp_path / "l2.jsonl"
    s1 = run_transcript_critique_loop(path1)
    s2 = run_transcript_critique_loop(path2)
    assert s1["topology"] == s2["topology"]


# 5. Repeated runs are byte-identical
def test_critique_loop_repeated_runs_byte_identical(tmp_path):
    path1 = tmp_path / "l1.jsonl"
    path2 = tmp_path / "l2.jsonl"
    s1 = run_transcript_critique_loop(path1)
    s2 = run_transcript_critique_loop(path2)
    assert json.dumps(s1, sort_keys=True, separators=(",", ":")) == \
           json.dumps(s2, sort_keys=True, separators=(",", ":"))


# 6. Execution replay ignores critique loop events
def test_execution_replay_ignores_critique_events(tmp_path):
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    writer.append({"type": "execution.event", "payload": {"step": 1}})

    run_transcript_critique_loop(path)

    writer2 = LedgerWriter(path)
    writer2.append({"type": "execution.event", "payload": {"step": 2}})

    exec_events = replay_execution_events(path)
    assert len(exec_events) == 2
    assert exec_events[0]["payload"] == {"step": 1}
    assert exec_events[1]["payload"] == {"step": 2}


# 7. Hash-chain verification passes
def test_critique_loop_hash_chain_passes(tmp_path):
    path = tmp_path / "ledger.jsonl"
    summary = run_transcript_critique_loop(path)
    assert summary["hash_chain_ok"] is True
    result = verify_mixed_ledger(path)
    assert result["ok"] is True
    assert result["failures"] == []
    assert result["count"] == 4


# 8. Canonical serialization preserved
def test_critique_loop_canonical_serialization(tmp_path):
    path = tmp_path / "ledger.jsonl"
    s1 = run_transcript_critique_loop(path)
    path2 = tmp_path / "l2.jsonl"
    s2 = run_transcript_critique_loop(path2)
    assert s1["canonical_output"] == s2["canonical_output"]
    parsed = json.loads(s1["canonical_output"])
    assert isinstance(parsed, list)
    assert len(parsed) == 4
    assert [e["role"] for e in parsed] == ["proposal", "critique", "critique", "arbiter"]


# Integration: unordered transcript input becomes parent-first after linearization
def test_linearization_applied_before_critique_processing(tmp_path):
    """Prove unordered append order → parent-first linearized thread."""
    path = tmp_path / "ledger.jsonl"

    TS_P = "2026-05-10T15:00:00+00:00"
    TS_CA = "2026-05-10T15:00:01+00:00"
    TS_CB = "2026-05-10T15:00:02+00:00"
    TS_ARB = "2026-05-10T15:00:03+00:00"
    RUN = "run_integ_test"

    proposal = make_transcript_event(
        run_id=RUN, sender="agent_a", recipient="broadcast",
        role="proposal", content="Integration proposal", created_at=TS_P,
    )
    critique_a = make_transcript_event(
        run_id=RUN, sender="agent_b", recipient="agent_a",
        role="critique", content="Critique A",
        created_at=TS_CA,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    critique_b = make_transcript_event(
        run_id=RUN, sender="agent_c", recipient="agent_a",
        role="critique", content="Critique B",
        created_at=TS_CB,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    arbiter = make_transcript_event(
        run_id=RUN, sender="agent_arbiter", recipient="broadcast",
        role="arbiter", content="Arbiter synthesis",
        created_at=TS_ARB,
        parent_message_id=critique_a["message_id"],
        references=[critique_a["message_id"], critique_b["message_id"], proposal["message_id"]],
    )

    # Append in reverse order (arbiter first) to simulate unordered input
    for event in [arbiter, critique_b, critique_a, proposal]:
        append_transcript_event(event, path)

    raw = replay_transcript_events(path)
    linearized = linearize_transcript_topology(raw)

    ids = [e["message_id"] for e in linearized]

    # Proposal is first
    assert ids[0] == proposal["message_id"]
    # Both critiques before arbiter
    assert ids.index(critique_a["message_id"]) < ids.index(arbiter["message_id"])
    assert ids.index(critique_b["message_id"]) < ids.index(arbiter["message_id"])
    # Proposal before all children
    for child_id in [critique_a["message_id"], critique_b["message_id"], arbiter["message_id"]]:
        assert ids.index(proposal["message_id"]) < ids.index(child_id)
    # Result is byte-stable
    assert ids == [e["message_id"] for e in linearize_transcript_topology(raw)]
