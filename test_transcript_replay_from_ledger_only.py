"""
Replay-from-ledger-only proof for transcript topology in a mixed ledger.

Proves transcript topology can be reconstructed using only persisted JSONL ledger
records even when the ledger also contains execution events. No in-memory event
objects or precomputed summaries are carried across the reconstruction boundary.
"""
import json
import tempfile
from pathlib import Path

from transcript_event import canonical_json, make_transcript_event
from transcript_ledger import (
    append_transcript_event,
    load_ledger_lines,
    replay_execution_events,
    replay_transcript_events,
    replay_transcript_topology,
    verify_mixed_ledger,
)
from transcript_topology import compute_transcript_linearization
from ledger_writer import LedgerWriter

RUN_ID = "run_mixed_ledger_proof"
TS_A = "2026-05-13T12:00:00+00:00"
TS_B = "2026-05-13T12:00:01+00:00"
TS_C = "2026-05-13T12:00:02+00:00"
TS_D = "2026-05-13T12:00:03+00:00"


def _build_mixed_ledger(path: Path) -> None:
    """
    Append two execution events interleaved with four transcript events,
    then discard all in-memory references.
    """
    # Execution event before transcript
    writer = LedgerWriter(path)
    writer.append({"event_type": "execution.step", "step": "init", "status": "ok"})

    proposal = make_transcript_event(
        RUN_ID, "agent_proposer", "broadcast", "proposal",
        "Add causal edge: fatigue -> error_rate", TS_A,
    )
    critique_a = make_transcript_event(
        RUN_ID, "agent_critic_a", "agent_proposer", "critique",
        "Edge weight unsubstantiated", TS_B,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    critique_b = make_transcript_event(
        RUN_ID, "agent_critic_b", "agent_proposer", "critique",
        "Alternative: fatigue -> stress -> error_rate", TS_C,
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

    # Execution event after transcript
    writer2 = LedgerWriter(path)
    writer2.append({"event_type": "execution.step", "step": "finalize", "status": "ok"})

    # Discard all in-memory event objects
    del proposal, critique_a, critique_b, arbiter, writer, writer2


# 1. Mixed ledger file contains correct total line count
def test_mixed_ledger_line_count(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_mixed_ledger(path)
    lines = [l for l in path.read_text().splitlines() if l.strip()]
    assert len(lines) == 6  # 2 execution + 4 transcript


# 2. load_ledger_lines returns all 6 records
def test_load_ledger_lines_returns_all_records(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_mixed_ledger(path)
    records = load_ledger_lines(path)
    assert len(records) == 6


# 3. Filtering transcript events from ledger returns exactly 4
def test_filter_transcript_events_from_mixed_ledger(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_mixed_ledger(path)
    events = replay_transcript_events(path)
    assert len(events) == 4
    assert all(e["event_type"] == "transcript.message" for e in events)


# 4. Execution events are filtered out — exactly 2 remain
def test_execution_events_isolated_from_transcript(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_mixed_ledger(path)
    exec_events = replay_execution_events(path)
    assert len(exec_events) == 2
    assert all(e["event_type"] == "execution.step" for e in exec_events)


# 5. Reconstruct topology from ledger-only records — no orphans
def test_reconstructed_topology_no_orphans(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_mixed_ledger(path)
    topo = replay_transcript_topology(path)
    assert topo["node_count"] == 4
    assert len(topo["order"]) == 4
    assert topo["orphaned"] == []
    assert len(topo["topology_hash"]) == 64


# 6. topology_hash from replay_transcript_topology matches compute_transcript_linearization
def test_topology_hash_consistent_from_mixed_ledger(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_mixed_ledger(path)
    topo = replay_transcript_topology(path)
    events = replay_transcript_events(path)
    lin = compute_transcript_linearization(events)
    assert topo["topology_hash"] == lin["topology_hash"]
    assert topo["order"] == lin["order"]
    assert topo["orphaned"] == lin["orphaned"]


# 7. Parent/reference relationships survive round-trip through mixed ledger
def test_parent_references_survive_mixed_ledger_roundtrip(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_mixed_ledger(path)
    events = replay_transcript_events(path)
    proposal = next(e for e in events if e["role"] == "proposal")
    critiques = [e for e in events if e["role"] == "critique"]
    arbiter = next(e for e in events if e["role"] == "arbiter")

    for c in critiques:
        assert c["parent_message_id"] == proposal["message_id"]
        assert proposal["message_id"] in c["references"]

    critique_ids = {c["message_id"] for c in critiques}
    assert set(arbiter["references"]) >= critique_ids | {proposal["message_id"]}


# 8. Two independent ledger reads produce byte-identical topology summary
def test_two_independent_reads_byte_identical(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_mixed_ledger(path)

    topo_a = replay_transcript_topology(path)
    events_a = replay_transcript_events(path)

    # Re-read independently
    topo_b = replay_transcript_topology(path)
    events_b = replay_transcript_events(path)

    assert canonical_json(topo_a) == canonical_json(topo_b)
    assert [e["message_id"] for e in events_a] == [e["message_id"] for e in events_b]


# 9. Orphan detection from ledger-only records — inject an orphan via raw append
def test_orphan_detected_from_ledger_only(tmp_path):
    path = tmp_path / "ledger.jsonl"
    # Build a clean ledger first
    proposal = make_transcript_event(
        RUN_ID, "agent_proposer", "broadcast", "proposal", "Test proposal", TS_A,
    )
    append_transcript_event(proposal, path)

    # Append an event whose parent is not in the ledger (orphan)
    orphan = make_transcript_event(
        RUN_ID, "agent_b", "agent_proposer", "critique", "Orphaned critique", TS_B,
        parent_message_id="tmsg_nonexistent000000000000",
    )
    # Bypass transcript_ledger validation to inject the orphan directly
    writer = LedgerWriter(path)
    writer.append(dict(orphan))
    del proposal, orphan, writer

    # Reload from ledger only and check orphan is reported
    topo = replay_transcript_topology(path)
    assert len(topo["orphaned"]) == 1


# 10. Hash-chain integrity passes for the full mixed ledger
def test_hash_chain_integrity_mixed_ledger(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_mixed_ledger(path)
    result = verify_mixed_ledger(path)
    assert result["ok"] is True
    assert result["count"] == 6
    assert result["failures"] == []


# 11. Raw JSONL lines for transcript events contain event_type == "transcript.message"
def test_raw_transcript_event_type_in_jsonl(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _build_mixed_ledger(path)
    lines = path.read_text().splitlines()
    records = [json.loads(l) for l in lines if l.strip()]
    transcript_records = [r for r in records if r.get("event_type") == "transcript.message"]
    assert len(transcript_records) == 4
    for r in transcript_records:
        assert "message_id" in r
        assert "rolling_hash" in r
