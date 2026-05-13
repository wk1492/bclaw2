from transcript_critique_loop import run_transcript_critique_loop
from transcript_ledger import (
    replay_execution_events,
    replay_transcript_events,
    replay_transcript_topology,
    verify_mixed_ledger,
)
from transcript_topology import compute_transcript_linearization
from replay_audit import compute_replay_audit
from transcript_diff import diff_transcript_events
from transcript_event import canonical_json


def _run(path):
    return run_transcript_critique_loop(path)


# 1. Full pipeline executes without exception and hash chain is intact
def test_full_pipeline_no_exception(tmp_path):
    result = _run(tmp_path / "ledger.jsonl")
    assert result["hash_chain_ok"] is True
    assert result["event_count"] == 4


# 2. verify_mixed_ledger reports clean after critique loop
def test_verify_mixed_ledger_ok(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _run(path)
    v = verify_mixed_ledger(path)
    assert v["ok"] is True
    assert v["count"] == 4
    assert v["failures"] == []


# 3. replay_transcript_events returns all 4 events with expected roles
def test_replay_transcript_events_count_and_roles(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _run(path)
    events = replay_transcript_events(path)
    assert len(events) == 4
    roles = {e["role"] for e in events}
    assert {"proposal", "critique", "arbiter"}.issubset(roles)


# 4. replay_execution_events is empty — pure transcript ledger has no execution events
def test_replay_execution_events_empty(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _run(path)
    assert replay_execution_events(path) == []


# 5. replay_transcript_topology returns no orphans and a non-empty order
def test_replay_transcript_topology_clean(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _run(path)
    topo = replay_transcript_topology(path)
    assert topo["node_count"] == 4
    assert len(topo["order"]) == 4
    assert topo["orphaned"] == []
    assert len(topo["topology_hash"]) == 64


# 6. compute_transcript_linearization order and topology_hash match replay_transcript_topology
def test_linearization_matches_topology(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _run(path)
    events = replay_transcript_events(path)
    lin = compute_transcript_linearization(events)
    topo = replay_transcript_topology(path)
    assert lin["order"] == topo["order"]
    assert lin["topology_hash"] == topo["topology_hash"]
    assert lin["orphaned"] == topo["orphaned"]


# 7. compute_replay_audit produces stable artifact_hash across two calls on same events
def test_compute_replay_audit_stable(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _run(path)
    events = replay_transcript_events(path)
    audit_a = compute_replay_audit(events)
    audit_b = compute_replay_audit(events)
    assert len(audit_a["artifact_hash"]) == 64
    assert audit_a["artifact_hash"] == audit_b["artifact_hash"]


# 8. diff of two independent identical runs reports no additions or removals
def test_diff_identical_runs_empty(tmp_path):
    result_a = _run(tmp_path / "a.jsonl")
    result_b = _run(tmp_path / "b.jsonl")
    events_a = replay_transcript_events(tmp_path / "a.jsonl")
    events_b = replay_transcript_events(tmp_path / "b.jsonl")
    diff = diff_transcript_events(events_a, events_b)
    assert diff["added"] == []
    assert diff["removed"] == []
    assert len(diff["unchanged"]) == 4
    # canonical_output from the loop itself is also byte-identical
    assert result_a["canonical_output"] == result_b["canonical_output"]


# 9. message_ids are deterministic (content-addressed) across two independent runs
def test_message_ids_stable_across_runs(tmp_path):
    _run(tmp_path / "a.jsonl")
    _run(tmp_path / "b.jsonl")
    events_a = replay_transcript_events(tmp_path / "a.jsonl")
    events_b = replay_transcript_events(tmp_path / "b.jsonl")
    assert [e["message_id"] for e in events_a] == [e["message_id"] for e in events_b]


# 10. replay_audit artifact_hash is identical across two independent runs
def test_replay_audit_hash_stable_across_runs(tmp_path):
    _run(tmp_path / "a.jsonl")
    _run(tmp_path / "b.jsonl")
    events_a = replay_transcript_events(tmp_path / "a.jsonl")
    events_b = replay_transcript_events(tmp_path / "b.jsonl")
    assert compute_replay_audit(events_a)["artifact_hash"] == \
           compute_replay_audit(events_b)["artifact_hash"]
