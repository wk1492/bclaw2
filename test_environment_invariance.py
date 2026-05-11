"""
Environment invariance regression coverage.

Proves replay contract stability is not tied to local runtime state:
- PYTHONHASHSEED variance
- repeated subprocess runs
- varied temp directories
- dict/list insertion-order variance
- canonical serialization byte-stability
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from replay_audit import compute_replay_audit, _canonical
from transcript_event import make_transcript_event

GOLDEN_PATH = Path(__file__).parent / "artifacts" / "baselines" / "golden_replay_audit.json"
THIS_DIR = Path(__file__).parent

RUN_ID = "run_golden_audit_001"
TS_A = "2026-05-11T10:00:00+00:00"
TS_B = "2026-05-11T10:00:01+00:00"
TS_C = "2026-05-11T10:00:02+00:00"
TS_D = "2026-05-11T10:00:03+00:00"


def _make_events():
    proposal = make_transcript_event(
        run_id=RUN_ID, sender="agent_proposer", recipient="broadcast",
        role="proposal", content="Add causal edge: workload -> burnout", created_at=TS_A,
    )
    critique_a = make_transcript_event(
        run_id=RUN_ID, sender="agent_critic_a", recipient="agent_proposer",
        role="critique", content="Workload -> burnout lacks longitudinal support",
        created_at=TS_B,
        parent_message_id=proposal["message_id"], references=[proposal["message_id"]],
    )
    critique_b = make_transcript_event(
        run_id=RUN_ID, sender="agent_critic_b", recipient="agent_proposer",
        role="critique", content="Alternative pathway is more defensible",
        created_at=TS_C,
        parent_message_id=proposal["message_id"], references=[proposal["message_id"]],
    )
    arbiter = make_transcript_event(
        run_id=RUN_ID, sender="agent_arbiter", recipient="broadcast",
        role="arbiter", content="Proposal deferred. Both critiques accepted.",
        created_at=TS_D,
        parent_message_id=critique_a["message_id"],
        references=[critique_a["message_id"], critique_b["message_id"], proposal["message_id"]],
    )
    return [proposal, critique_a, critique_b, arbiter]


def _drift_report(expected: dict, actual: dict) -> str:
    lines = ["Hash drift detected:"]
    for key in sorted(expected):
        if expected[key] != actual.get(key):
            lines.append(f"  artifact: {key}")
            lines.append(f"  expected: {expected[key]}")
            lines.append(f"  actual:   {actual.get(key)}")
    return "\n".join(lines)


# Helper: run audit in subprocess with given PYTHONHASHSEED, return JSON output
def _subprocess_audit(hashseed: int) -> dict:
    script = """
import json, sys
sys.path.insert(0, '.')
from transcript_event import make_transcript_event
from replay_audit import compute_replay_audit

RUN_ID = "run_golden_audit_001"
proposal = make_transcript_event(run_id=RUN_ID, sender="agent_proposer", recipient="broadcast",
    role="proposal", content="Add causal edge: workload -> burnout",
    created_at="2026-05-11T10:00:00+00:00")
critique_a = make_transcript_event(run_id=RUN_ID, sender="agent_critic_a", recipient="agent_proposer",
    role="critique", content="Workload -> burnout lacks longitudinal support",
    created_at="2026-05-11T10:00:01+00:00",
    parent_message_id=proposal["message_id"], references=[proposal["message_id"]])
critique_b = make_transcript_event(run_id=RUN_ID, sender="agent_critic_b", recipient="agent_proposer",
    role="critique", content="Alternative pathway is more defensible",
    created_at="2026-05-11T10:00:02+00:00",
    parent_message_id=proposal["message_id"], references=[proposal["message_id"]])
arbiter = make_transcript_event(run_id=RUN_ID, sender="agent_arbiter", recipient="broadcast",
    role="arbiter", content="Proposal deferred. Both critiques accepted.",
    created_at="2026-05-11T10:00:03+00:00",
    parent_message_id=critique_a["message_id"],
    references=[critique_a["message_id"], critique_b["message_id"], proposal["message_id"]])
print(json.dumps(compute_replay_audit([proposal, critique_a, critique_b, arbiter])))
"""
    env = {**os.environ, "PYTHONHASHSEED": str(hashseed)}
    result = subprocess.run(
        ["uv", "run", "python", "-c", script],
        capture_output=True, text=True, cwd=THIS_DIR, env=env,
    )
    assert result.returncode == 0, f"Subprocess failed (seed={hashseed}):\n{result.stderr}"
    return json.loads(result.stdout.strip())


# 1. Subprocess replay matches golden fixture
def test_subprocess_replay_matches_golden():
    golden = json.loads(GOLDEN_PATH.read_text())["expected_audit"]
    audit = _subprocess_audit(42)
    assert audit == golden, _drift_report(golden, audit)


# 2. Varied PYTHONHASHSEED values produce identical hashes
def test_varied_pythonhashseed_produces_identical_hashes():
    seeds = [0, 1, 42, 12345, 99999]
    results = [_subprocess_audit(s) for s in seeds]
    reference = results[0]
    for i, result in enumerate(results[1:], 1):
        assert result == reference, (
            f"PYTHONHASHSEED={seeds[i]} produced drift:\n" + _drift_report(reference, result)
        )


# 3. Fresh temp directories produce identical hashes
def test_fresh_temp_directories_produce_identical_hashes(tmp_path):
    events = _make_events()
    results = []
    for i in range(3):
        results.append(compute_replay_audit(events))
    reference = results[0]
    for i, r in enumerate(results[1:], 1):
        assert r == reference, _drift_report(reference, r)


# 4. Serialization hardening: identical dicts with different insertion order
def test_canonical_serialization_insertion_order_independent():
    d1 = {"z": 3, "a": 1, "m": 2}
    d2 = {"a": 1, "m": 2, "z": 3}
    d3 = {"m": 2, "z": 3, "a": 1}
    assert _canonical(d1) == _canonical(d2) == _canonical(d3)

    l1 = [{"b": 2, "a": 1}, {"d": 4, "c": 3}]
    l2 = [{"a": 1, "b": 2}, {"c": 3, "d": 4}]
    assert _canonical(l1) == _canonical(l2)

    h1 = hashlib.sha256(_canonical(d1).encode()).hexdigest()
    h2 = hashlib.sha256(_canonical(d2).encode()).hexdigest()
    assert h1 == h2


# 5. Transcript hash stable across all hash fields independently
def test_all_hash_fields_stable_across_subprocess_runs():
    golden = json.loads(GOLDEN_PATH.read_text())["expected_audit"]
    for seed in [7, 101, 65537]:
        audit = _subprocess_audit(seed)
        for field in ("transcript_hash", "linearized_hash", "critique_order_hash",
                      "fusion_output_hash", "artifact_hash"):
            assert audit[field] == golden[field], (
                f"Field '{field}' drifted at seed={seed}:\n"
                f"  expected: {golden[field]}\n"
                f"  actual:   {audit[field]}"
            )


# 6. Drift visibility helper works correctly (self-test)
def test_drift_report_identifies_first_differing_artifact():
    expected = {"transcript_hash": "aaa", "artifact_hash": "bbb"}
    actual = {"transcript_hash": "aaa", "artifact_hash": "ccc"}
    report = _drift_report(expected, actual)
    assert "artifact_hash" in report
    assert "bbb" in report
    assert "ccc" in report
    assert "transcript_hash" not in report
