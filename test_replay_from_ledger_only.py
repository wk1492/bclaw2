"""
Replay-from-ledger-only reconstruction proof.

Proves the transcript substrate can be fully reconstructed from the persisted
JSONL ledger with no reliance on in-memory event objects or hidden state.

All reconstruction steps use only the public replay/topology API on the
persisted file. In-memory event objects are explicitly deleted before reconstruction.
"""
import json
import tempfile
from pathlib import Path

from transcript_event import canonical_json, make_transcript_event
from transcript_ledger import (
    append_transcript_event,
    replay_execution_events,
    replay_transcript_events,
    replay_transcript_topology,
    verify_mixed_ledger,
)
from transcript_topology import compute_transcript_linearization
from replay_audit import compute_replay_audit

RUN_ID = "run_ledger_only_proof"
TS_A = "2026-05-13T11:00:00+00:00"
TS_B = "2026-05-13T11:00:01+00:00"
TS_C = "2026-05-13T11:00:02+00:00"
TS_D = "2026-05-13T11:00:03+00:00"


def _build_ledger(path: Path) -> None:
    """Append 4 deterministic events then discard all in-memory references."""
    proposal = make_transcript_event(
        RUN_ID, "agent_proposer", "broadcast", "proposal",
        "Add causal edge: workload -> burnout", TS_A,
    )
    critique_a = make_transcript_event(
        RUN_ID, "agent_critic_a", "agent_proposer", "critique",
        "Lacks longitudinal support", TS_B,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    critique_b = make_transcript_event(
        RUN_ID, "agent_critic_b", "agent_proposer", "critique",
        "Indirect pathway is more defensible", TS_C,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    arbiter = make_transcript_event(
        RUN_ID, "agent_arbiter", "broadcast", "arbiter",
        "Proposal deferred. Both critiques accepted.", TS_D,
        parent_message_id=critique_a["message_id"],
        references=[critique_a["message_id"], critique_b["message_id"],
                    proposal["message_id"]],
    )
    for event in [proposal, critique_a, critique_b, arbiter]:
        append_transcript_event(event, path)
    # Explicitly discard all in-memory event objects
    del proposal, critique_a, critique_b, arbiter


# 1. Ledger file is created and non-empty after append
def test_ledger_file_exists_after_append(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_ledger(path)
    assert path.exists()
    lines = [l for l in path.read_text().splitlines() if l.strip()]
    assert len(lines) == 4


# 2. Reconstruct events solely from persisted JSONL — correct count and roles
def test_reconstruct_events_from_ledger_only(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_ledger(path)
    del path  # rebind to prove we re-open by path only
    path = tmp_path / "ledger.jsonl"

    events = replay_transcript_events(path)
    assert len(events) == 4
    roles = {e["role"] for e in events}
    assert {"proposal", "critique", "arbiter"}.issubset(roles)


# 3. Reconstructed linearized order is non-empty with no orphans
def test_reconstructed_topology_no_orphans(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_ledger(path)

    topo = replay_transcript_topology(path)
    assert topo["node_count"] == 4
    assert len(topo["order"]) == 4
    assert topo["orphaned"] == []


# 4. topology_hash from ledger replay matches compute_transcript_linearization
def test_topology_hash_consistent_across_two_paths(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_ledger(path)

    topo = replay_transcript_topology(path)
    events = replay_transcript_events(path)
    lin = compute_transcript_linearization(events)

    assert topo["topology_hash"] == lin["topology_hash"]
    assert topo["order"] == lin["order"]
    assert topo["orphaned"] == lin["orphaned"]


# 5. Parent/reference relationships survive round-trip through ledger
def test_parent_reference_relationships_preserved(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_ledger(path)

    events = replay_transcript_events(path)
    by_role = {e["role"]: e for e in events if e["role"] != "critique"}
    critiques = [e for e in events if e["role"] == "critique"]

    proposal_id = by_role["proposal"]["message_id"]
    arbiter_id = by_role["arbiter"]["message_id"]

    # Both critiques reference the proposal
    for c in critiques:
        assert c["parent_message_id"] == proposal_id
        assert proposal_id in c["references"]

    # Arbiter references both critiques and proposal
    arbiter = by_role["arbiter"]
    critique_ids = {c["message_id"] for c in critiques}
    assert set(arbiter["references"]) >= critique_ids | {proposal_id}


# 6. Replay summary (compute_replay_audit) reconstructed from ledger only
def test_replay_audit_from_ledger_only(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_ledger(path)

    events = replay_transcript_events(path)
    audit = compute_replay_audit(events)
    assert len(audit["artifact_hash"]) == 64
    assert audit["artifact_hash"] == audit["artifact_hash"].lower()


# 7. Two independent reconstructions from same ledger produce byte-identical canonical output
def test_two_reconstructions_byte_identical(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_ledger(path)

    events_a = replay_transcript_events(path)
    topo_a = replay_transcript_topology(path)
    audit_a = compute_replay_audit(events_a)

    # Second reconstruction — re-read file independently
    events_b = replay_transcript_events(path)
    topo_b = replay_transcript_topology(path)
    audit_b = compute_replay_audit(events_b)

    assert canonical_json(topo_a) == canonical_json(topo_b)
    assert audit_a["artifact_hash"] == audit_b["artifact_hash"]
    assert [e["message_id"] for e in events_a] == [e["message_id"] for e in events_b]


# 8. Execution replay sees no events — ledger is transcript-only
def test_execution_replay_empty(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_ledger(path)
    assert replay_execution_events(path) == []


# 9. Hash-chain validation passes on reconstructed ledger
def test_hash_chain_valid_after_reconstruction(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_ledger(path)

    result = verify_mixed_ledger(path)
    assert result["ok"] is True
    assert result["count"] == 4
    assert result["failures"] == []


# 10. Raw JSONL lines are valid JSON with required chain fields
def test_raw_jsonl_lines_have_chain_fields(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_ledger(path)

    lines = [l for l in path.read_text().splitlines() if l.strip()]
    prev_hash = "0" * 64
    for line in lines:
        record = json.loads(line)
        assert "event_hash" in record
        assert "rolling_hash" in record
        assert "previous_hash" in record
        assert record["previous_hash"] == prev_hash
        prev_hash = record["rolling_hash"]


# 11. event_count from topology matches raw JSONL line count
def test_event_count_matches_raw_line_count(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_ledger(path)

    raw_lines = [l for l in path.read_text().splitlines() if l.strip()]
    topo = replay_transcript_topology(path)
    assert topo["node_count"] == len(raw_lines)


# 12. Ledger is append-only: file size only grows, never shrinks after each append
def test_ledger_grows_monotonically(tmp_path):
    path = tmp_path / "ledger.jsonl"
    sizes = []
    for ts, role, content in [
        (TS_A, "proposal", "Prop A"),
        (TS_B, "critique", "Crit B"),
        (TS_C, "arbiter", "Arb C"),
    ]:
        # Build events sequentially to respect parent chain
        events = replay_transcript_events(path) if path.exists() else []
        parent_id = events[-1]["message_id"] if events else None
        refs = [events[-1]["message_id"]] if events else []
        event = make_transcript_event(
            RUN_ID, "agent_x", "broadcast", role, content, ts,
            parent_message_id=parent_id, references=refs,
        )
        append_transcript_event(event, path)
        sizes.append(path.stat().st_size)

    assert sizes[0] < sizes[1] < sizes[2]
