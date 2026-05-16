"""
BCLAW4 Experiment 004 — transcript-derived state engine.
Branch: bclaw4-chaos-lab-001.
"""
import json
import os
import tempfile
from pathlib import Path

from bclaw4_state_engine import RUN_ID, reduce_transcript_state, run_state_engine


def _run():
    return run_state_engine()


# 1. Reducer produces expected counts for proposal+critique+critique+arbiter exchange
def test_reducer_produces_expected_counts():
    state = _run()["derived_state"]
    assert state["proposal_count"]   == 1
    assert state["critique_count"]   == 2
    assert state["accepted_count"]   == 2  # both critiques referenced by arbiter
    assert state["rejected_count"]   == 1  # proposal has accepted critiques against it
    assert state["unresolved_count"] == 0
    assert state["last_status"]      == "arbiter"
    assert len(state["thread_ids"])  == 4  # proposal + 2 critiques + arbiter
    assert len(state["transcript_hash"]) == 64


# 2. Replay reproduces identical state
def test_replay_reproduces_identical_state():
    from transcript_ledger import replay_transcript_events
    result = _run()
    events = replay_transcript_events(result["ledger_path"])
    comm_events = [e for e in events if e["role"] != "system"]
    fresh_state = reduce_transcript_state(comm_events)
    assert fresh_state == result["derived_state"]


# 3. Shuffled ordering converges to identical state
def test_shuffled_ordering_converges_identically():
    from transcript_ledger import replay_transcript_events
    result = _run()
    events = replay_transcript_events(result["ledger_path"])
    comm_events = [e for e in events if e["role"] != "system"]
    assert reduce_transcript_state(comm_events) == reduce_transcript_state(list(reversed(comm_events)))


# 4. Byte-identical JSON serialization across runs
def test_byte_identical_json_serialization():
    stable = {"summary_id", "run_id", "derived_state", "snapshot_message_id", "chain_ok", "event_count"}
    runs = [_run() for _ in range(3)]
    snapshots = [
        json.dumps({k: r[k] for k in stable}, sort_keys=True, separators=(",", ":"))
        for r in runs
    ]
    assert len(set(snapshots)) == 1, f"output varied: {set(snapshots)}"


# 5. transcript_hash is a deterministic 64-char hex string
def test_transcript_hash_deterministic():
    h1 = _run()["derived_state"]["transcript_hash"]
    h2 = _run()["derived_state"]["transcript_hash"]
    assert h1 == h2
    assert len(h1) == 64
    assert all(c in "0123456789abcdef" for c in h1)


# 6. Duplicate events are handled deterministically (deduped by message_id)
def test_duplicate_event_handling_deterministic():
    from transcript_ledger import replay_transcript_events
    result = _run()
    events = replay_transcript_events(result["ledger_path"])
    comm = [e for e in events if e["role"] != "system"]
    state_once  = reduce_transcript_state(comm)
    state_duped = reduce_transcript_state(comm + comm)
    assert state_once == state_duped


# 7. Hash-chain verification passes after all appends
def test_hash_chain_verification_passes():
    result = _run()
    assert result["chain_ok"] is True
    assert result["event_count"] == 5  # 4 comm + 1 snapshot


# 8. Execution replay isolation preserved
def test_execution_replay_isolation_preserved():
    from transcript_ledger import replay_execution_events
    result = _run()
    assert replay_execution_events(result["ledger_path"]) == []


# 9. Existing critique loop is unaffected (regression check)
def test_existing_critique_loop_unaffected():
    from transcript_critique_loop import run_transcript_critique_loop

    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    Path(path).unlink()
    result = run_transcript_critique_loop(Path(path))
    assert result["hash_chain_ok"] is True
    assert result["event_count"] == 4
    assert result["roles"] == ["proposal", "critique", "critique", "arbiter"]


# 10. No baseline artifacts modified by running the engine
def test_no_baseline_artifacts_modified():
    baseline = Path("docs/baselines/BCLAW2_STABLE_CHECKPOINT_c8d4653.md")
    before = baseline.read_text()
    _run()
    assert baseline.read_text() == before
