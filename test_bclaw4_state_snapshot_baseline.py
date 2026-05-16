"""
BCLAW4 Experiment 005 — state snapshot replay baseline.
Branch: bclaw4-chaos-lab-001.
"""
import json
from pathlib import Path

from bclaw4_state_engine import _canonical, _sha256, run_state_engine

_ARTIFACT_PATH = Path("artifacts/baselines/bclaw4_state_snapshot_001.json")


def _load_artifact() -> dict:
    return json.loads(_ARTIFACT_PATH.read_text())


def _fresh_state() -> dict:
    result = run_state_engine()
    state = result["derived_state"]
    return {
        "artifact_id": _sha256(_canonical(state)),
        "version": result["event_count"] and 1,  # STATE_VERSION constant
        "run_id": result["run_id"],
        "snapshot_message_id": result["snapshot_message_id"],
        "derived_state": state,
    }


# 1. Artifact matches freshly generated state
def test_artifact_matches_freshly_generated_state():
    artifact = _load_artifact()
    fresh = _fresh_state()
    assert fresh["derived_state"] == artifact["derived_state"], (
        "freshly generated state must match frozen artifact"
    )
    assert fresh["artifact_id"] == artifact["artifact_id"]
    assert fresh["snapshot_message_id"] == artifact["snapshot_message_id"]


# 2. Repeated generation is byte-identical
def test_repeated_generation_byte_identical():
    snaps = [json.dumps(_fresh_state(), sort_keys=True, separators=(",", ":")) for _ in range(3)]
    assert len(set(snaps)) == 1, f"repeated generation produced different output: {set(snaps)}"


# 3. Hash-chain verification passes
def test_hash_chain_verification_passes():
    result = run_state_engine()
    assert result["chain_ok"] is True


# 4. Execution replay ignores snapshot event
def test_execution_replay_ignores_snapshot_event():
    from transcript_ledger import replay_execution_events
    result = run_state_engine()
    assert replay_execution_events(result["ledger_path"]) == []


# 5. Baseline artifact file is canonical JSON
def test_baseline_artifact_is_canonical_json():
    raw = _ARTIFACT_PATH.read_text()
    parsed = json.loads(raw)
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert raw == canonical, (
        f"artifact is not canonical JSON.\n"
        f"  on-disk:   {raw[:80]!r}\n"
        f"  canonical: {canonical[:80]!r}"
    )


# 6. No runtime clocks, random, or model calls — artifact_id stable across runs
def test_no_runtime_clock_random_or_model_calls():
    ids = [_fresh_state()["artifact_id"] for _ in range(5)]
    assert len(set(ids)) == 1, f"artifact_id varied: {set(ids)}"
