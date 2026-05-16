"""
BCLAW4 Experiment 003 — communication-computation loop.
Branch: bclaw4-chaos-lab-001.
"""
import json
from pathlib import Path

from bclaw4_comm_compute_loop import (
    RUN_ID,
    compute_transcript_score,
    run_comm_compute_loop,
)


def _run():
    return run_comm_compute_loop()


# 1. Communication events are emitted
def test_communication_events_are_emitted():
    from transcript_ledger import replay_transcript_events
    result = _run()
    events = replay_transcript_events(result["ledger_path"])
    roles = [e["role"] for e in events]
    assert "proposal" in roles
    assert "critique" in roles
    assert "arbiter" in roles


# 2. Deterministic computation result is emitted as a system event
def test_deterministic_computation_result_emitted():
    from transcript_ledger import replay_transcript_events
    result = _run()
    events = replay_transcript_events(result["ledger_path"])
    system_events = [e for e in events if e["role"] == "system"]
    assert len(system_events) == 1, "exactly one system event expected"
    score = json.loads(system_events[0]["content"])
    for key in ("message_count", "critique_count", "unresolved_count", "arbitration_status"):
        assert key in score, f"missing score key: {key}"


# 3. Computation result depends only on replayed transcript state
def test_computation_depends_only_on_replayed_transcript_state():
    from transcript_ledger import replay_transcript_events
    result = _run()
    all_events = replay_transcript_events(result["ledger_path"])

    system_event = next(e for e in all_events if e["role"] == "system")
    embedded_score = json.loads(system_event["content"])
    assert embedded_score == result["computation"], (
        "score embedded in system event must match reported computation"
    )

    comm_events = [e for e in all_events if e["role"] != "system"]
    fresh_score = compute_transcript_score(comm_events)
    assert fresh_score == result["computation"], (
        "fresh computation from replayed comm events must match reported computation"
    )


# 4. Repeated runs produce byte-identical deterministic output
def test_repeated_runs_produce_byte_identical_output():
    stable = {"summary_id", "run_id", "communication", "computation",
              "result_message_id", "chain_ok", "event_count"}
    runs = [_run() for _ in range(3)]
    snapshots = [
        json.dumps({k: r[k] for k in stable}, sort_keys=True, separators=(",", ":"))
        for r in runs
    ]
    assert len(set(snapshots)) == 1, f"output varied across runs: {snapshots}"


# 5. compute_transcript_score is order-independent
def test_shuffled_input_computes_same_score():
    from transcript_ledger import replay_transcript_events
    result = _run()
    all_events = replay_transcript_events(result["ledger_path"])
    comm_events = [e for e in all_events if e["role"] != "system"]

    score_forward = compute_transcript_score(comm_events)
    score_reversed = compute_transcript_score(list(reversed(comm_events)))
    assert score_forward == score_reversed, (
        "compute_transcript_score must be order-independent"
    )


# 6. Hash-chain verification passes after all appends
def test_hash_chain_verification_passes():
    result = _run()
    assert result["chain_ok"] is True, f"chain verification failed: {result}"
    assert result["event_count"] == 4  # proposal + critique + arbiter + system


# 7. Execution replay ignores all BCLAW4 transcript events
def test_execution_replay_ignores_transcript_events():
    from transcript_ledger import replay_execution_events
    result = _run()
    assert replay_execution_events(result["ledger_path"]) == [], (
        "execution replay must return [] — all events are transcript.message type"
    )


# 8. No runtime clocks or random — summary_id stable across N runs
def test_no_runtime_clock_random_or_model_calls():
    ids = [_run()["summary_id"] for _ in range(5)]
    assert len(set(ids)) == 1, f"summary_id varied: {set(ids)}"


# 9. No baseline artifacts changed by running the loop
def test_no_baseline_artifacts_changed():
    baseline = Path("docs/baselines/BCLAW2_STABLE_CHECKPOINT_c8d4653.md")
    content_before = baseline.read_text()
    _run()
    content_after = baseline.read_text()
    assert content_before == content_after, "running the loop must not mutate existing baselines"
