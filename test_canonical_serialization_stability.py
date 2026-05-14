"""
Canonical serialization stability audit.

Proves canonical_json and content-addressed IDs are stable across:
  deepcopy, repeated calls, insertion-order variance, PYTHONHASHSEED variance.

Audited objects:
  - transcript event
  - transcript topology output (compute_transcript_linearization)
  - transcript replay summary (compute_replay_audit)
  - runner payload (run_proposal)
  - diff object (diff_transcript_events)

No production code changes. Existing helpers only.
Full PYTHONHASHSEED subprocess coverage lives in test_environment_invariance.py;
one focused canonical_json subprocess check is included here.
"""
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from transcript_event import canonical_json, make_transcript_event
from transcript_topology import compute_transcript_linearization
from replay_audit import compute_replay_audit
from model_runner import run_proposal
from transcript_diff import diff_transcript_events

RUN_ID = "run_stability_audit"
TS_A = "2026-05-13T10:00:00+00:00"
TS_B = "2026-05-13T10:00:01+00:00"
TS_C = "2026-05-13T10:00:02+00:00"


def _make_events():
    proposal = make_transcript_event(
        RUN_ID, "agent_a", "broadcast", "proposal", "Add causal edge", TS_A,
    )
    critique = make_transcript_event(
        RUN_ID, "agent_b", "agent_a", "critique", "Edge lacks support", TS_B,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    arbiter = make_transcript_event(
        RUN_ID, "agent_arbiter", "broadcast", "arbiter", "Proposal deferred", TS_C,
        parent_message_id=critique["message_id"],
        references=[critique["message_id"], proposal["message_id"]],
    )
    return [proposal, critique, arbiter]


# ── Transcript event ─────────────────────────────────────────────────────────

def test_event_deepcopy_canonical_identical():
    for e in _make_events():
        assert canonical_json(e) == canonical_json(copy.deepcopy(e))


def test_event_repeated_serialization_byte_identical():
    e = _make_events()[0]
    results = [canonical_json(e) for _ in range(8)]
    assert len(set(results)) == 1


def test_event_insertion_order_invariant():
    e = _make_events()[0]
    shuffled = dict(reversed(list(e.items())))
    assert canonical_json(e) == canonical_json(shuffled)


def test_event_frozen_golden_canonical_string():
    assert canonical_json({"a": 1, "b": "hello", "c": [1, 2]}) == '{"a":1,"b":"hello","c":[1,2]}'
    assert canonical_json({"z": "z", "a": "a"}) == '{"a":"a","z":"z"}'


def test_event_no_float_or_runtime_values():
    for e in _make_events():
        parsed = json.loads(canonical_json(e))
        for v in parsed.values():
            assert not isinstance(v, float), f"float in event canonical output: {v}"


# ── Transcript topology output ───────────────────────────────────────────────

def test_topology_deepcopy_canonical_identical():
    lin = compute_transcript_linearization(_make_events())
    assert canonical_json(lin) == canonical_json(copy.deepcopy(lin))


def test_topology_repeated_calls_byte_identical():
    events = _make_events()
    results = [canonical_json(compute_transcript_linearization(events)) for _ in range(5)]
    assert len(set(results)) == 1


def test_topology_hash_is_pure_function_of_order():
    """topology_hash == sha256(canonical(order)) — no event content leaks in."""
    lin = compute_transcript_linearization(_make_events())
    expected = hashlib.sha256(
        json.dumps(lin["order"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        .encode("utf-8")
    ).hexdigest()
    assert lin["topology_hash"] == expected


def test_topology_hash_format():
    lin = compute_transcript_linearization(_make_events())
    h = lin["topology_hash"]
    assert len(h) == 64
    assert h == h.lower()
    assert all(c in "0123456789abcdef" for c in h)


def test_topology_shuffled_input_identical_hash():
    events = _make_events()
    lin_fwd = compute_transcript_linearization(events)
    lin_rev = compute_transcript_linearization(list(reversed(events)))
    assert lin_fwd["topology_hash"] == lin_rev["topology_hash"]
    assert lin_fwd["order"] == lin_rev["order"]


# ── Transcript replay summary (compute_replay_audit) ────────────────────────

def test_audit_deepcopy_canonical_identical():
    audit = compute_replay_audit(_make_events())
    assert canonical_json(audit) == canonical_json(copy.deepcopy(audit))


def test_audit_repeated_calls_byte_identical():
    events = _make_events()
    results = [canonical_json(compute_replay_audit(events)) for _ in range(5)]
    assert len(set(results)) == 1


def test_audit_artifact_hash_format_and_stability():
    audit = compute_replay_audit(_make_events())
    h = audit["artifact_hash"]
    assert len(h) == 64 and h == h.lower()
    assert all(c in "0123456789abcdef" for c in h)
    # Second call identical
    assert compute_replay_audit(_make_events())["artifact_hash"] == h


# ── Runner payload ───────────────────────────────────────────────────────────

def test_runner_payload_deepcopy_canonical_identical():
    payload = run_proposal(RUN_ID, "agent_a", "agent_b", "proposal", "test prompt")
    assert canonical_json(payload) == canonical_json(copy.deepcopy(payload))


def test_runner_payload_repeated_calls_byte_identical():
    kwargs = dict(run_id=RUN_ID, sender="a", recipient="b", role="proposal", prompt="test")
    results = [canonical_json(run_proposal(**kwargs)) for _ in range(5)]
    assert len(set(results)) == 1


def test_runner_payload_no_timestamps_or_floats():
    payload = run_proposal(RUN_ID, "a", "b", "proposal", "stability check")
    banned = {"timestamp", "created_at", "event_id", "event_hash",
              "rolling_hash", "previous_hash"}
    assert banned.isdisjoint(payload.keys())
    for v in payload.values():
        assert not isinstance(v, float)


# ── Diff object ──────────────────────────────────────────────────────────────

def test_diff_deepcopy_canonical_identical():
    events = _make_events()
    diff = diff_transcript_events(events, events)
    assert canonical_json(diff) == canonical_json(copy.deepcopy(diff))


def test_diff_repeated_calls_byte_identical():
    events = _make_events()
    results = [canonical_json(diff_transcript_events(events, events)) for _ in range(5)]
    assert len(set(results)) == 1


# ── PYTHONHASHSEED subprocess (focused on canonical_json + message_id) ───────

_SEED_SCRIPT = """\
import sys, json
sys.path.insert(0, ".")
from transcript_event import canonical_json, make_transcript_event
e = make_transcript_event(
    "run_hashseed_check", "agent_a", "broadcast", "proposal",
    "Add causal edge", "2026-05-13T10:00:00+00:00",
)
print(canonical_json({"a": 3, "z": 1, "m": "hello"}))
print(e["message_id"])
"""


def _run_seed(seed: int) -> tuple:
    env = {**os.environ, "PYTHONHASHSEED": str(seed)}
    r = subprocess.run(
        [sys.executable, "-c", _SEED_SCRIPT],
        capture_output=True, text=True, env=env,
        cwd=str(Path(__file__).parent),
    )
    assert r.returncode == 0, f"seed={seed} failed:\n{r.stderr}"
    lines = r.stdout.strip().splitlines()
    return lines[0], lines[1]


def test_canonical_json_stable_across_pythonhashseeds():
    results = [_run_seed(s) for s in (0, 1, 42, 99, 12345)]
    canonical_outputs, message_ids = zip(*results)
    assert len(set(canonical_outputs)) == 1, f"canonical diverged: {canonical_outputs}"
    assert len(set(message_ids)) == 1, f"message_id diverged: {message_ids}"
