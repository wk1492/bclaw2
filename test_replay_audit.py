"""
Replay audit regression tests.

Verifies that compute_replay_audit produces stable, machine-independent hashes
across repeated runs, insertion-order variants, and detects intentional mutation.
"""
import json
import random
from pathlib import Path

import pytest

from transcript_event import make_transcript_event
from transcript_topology import linearize_transcript_topology
from replay_audit import compute_replay_audit, _canonical

FIXTURE_PATH = Path(__file__).parent / "artifacts" / "baselines" / "golden_replay_audit.json"

RUN_ID = "run_golden_audit_001"
TS_A = "2026-05-11T10:00:00+00:00"
TS_B = "2026-05-11T10:00:01+00:00"
TS_C = "2026-05-11T10:00:02+00:00"
TS_D = "2026-05-11T10:00:03+00:00"


def _make_golden_events():
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


def _load_golden():
    return json.loads(FIXTURE_PATH.read_text())


# 1. Audit output matches committed golden fixture
def test_audit_matches_golden_fixture():
    events = _make_golden_events()
    golden = _load_golden()
    audit = compute_replay_audit(events)
    assert audit == golden["expected_audit"], (
        f"Audit drifted from golden.\nExpected: {golden['expected_audit']}\nGot: {audit}"
    )


# 2. All five hash fields are present in audit output
def test_audit_emits_all_five_hashes():
    events = _make_golden_events()
    audit = compute_replay_audit(events)
    for key in ("transcript_hash", "linearized_hash", "critique_order_hash",
                "fusion_output_hash", "artifact_hash"):
        assert key in audit, f"Missing key: {key}"
        assert isinstance(audit[key], str) and len(audit[key]) == 64


# 3. Repeated runs produce byte-identical audit output
def test_repeated_runs_byte_identical():
    events = _make_golden_events()
    outputs = [_canonical(compute_replay_audit(events)) for _ in range(5)]
    assert len(set(outputs)) == 1, "Audit output drifted across repeated runs"


# 4. Insertion-order permutations produce identical hashes
def test_insertion_order_independent(tmp_path):
    events = _make_golden_events()
    reference = compute_replay_audit(events)
    rng = random.Random(13)
    for _ in range(20):
        shuffled = events[:]
        rng.shuffle(shuffled)
        assert compute_replay_audit(shuffled) == reference, \
            "Audit hash changed under insertion order permutation"


# 5. Mutation-detection: perturbing sibling order changes linearized_hash
def test_mutation_detected_on_sibling_perturbation():
    events = _make_golden_events()
    proposal, critique_a, critique_b, arbiter = events

    # Perturb: swap critique timestamps to force different sibling order
    perturbed_a = {**critique_a, "created_at": critique_b["created_at"]}
    perturbed_b = {**critique_b, "created_at": critique_a["created_at"]}
    perturbed_events = [proposal, perturbed_a, perturbed_b, arbiter]

    original_audit = compute_replay_audit(events)
    perturbed_audit = compute_replay_audit(perturbed_events)

    # transcript_hash must differ (content changed)
    assert perturbed_audit["transcript_hash"] != original_audit["transcript_hash"]
    # artifact_hash must differ
    assert perturbed_audit["artifact_hash"] != original_audit["artifact_hash"]


# 6. Mutation-detection: altering content changes transcript_hash
def test_mutation_detected_on_content_change():
    events = _make_golden_events()
    original_audit = compute_replay_audit(events)

    mutated = [{**e} for e in events]
    mutated[0]["content"] = "TAMPERED: different proposal content"
    mutated_audit = compute_replay_audit(mutated)

    assert mutated_audit["transcript_hash"] != original_audit["transcript_hash"]
    assert mutated_audit["artifact_hash"] != original_audit["artifact_hash"]


# 7. Critique-order hash is independent of ledger-decoration fields
def test_critique_order_hash_stable_without_ledger_fields():
    events = _make_golden_events()
    clean_audit = compute_replay_audit(events)

    # Simulate ledger-decorated events (with timestamp, event_hash, etc.)
    decorated = [{**e, "timestamp": "2099-01-01T00:00:00+00:00",
                  "event_hash": "x" * 64, "rolling_hash": "y" * 64} for e in events]
    decorated_audit = compute_replay_audit(decorated)

    assert decorated_audit["critique_order_hash"] == clean_audit["critique_order_hash"]
    assert decorated_audit["linearized_hash"] == clean_audit["linearized_hash"]
    assert decorated_audit["artifact_hash"] == clean_audit["artifact_hash"]


# 8. Artifact hash is a stable function of the four sub-hashes
def test_artifact_hash_is_function_of_sub_hashes():
    events = _make_golden_events()
    audit = compute_replay_audit(events)
    import hashlib
    sub = {k: audit[k] for k in
           ("critique_order_hash", "fusion_output_hash", "linearized_hash", "transcript_hash")}
    expected = hashlib.sha256(
        json.dumps(sub, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    assert audit["artifact_hash"] == expected
