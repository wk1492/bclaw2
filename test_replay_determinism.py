"""
Replay determinism regression coverage.

Proves critique topology integration preserves byte-stable determinism across:
- repeated pipeline runs
- ledger hash stability
- critique ordering stability
- arbitration output stability
- randomized sibling insertion order
"""
import json
import random

from transcript_critique_loop import run_transcript_critique_loop
from transcript_event import make_transcript_event, canonical_json
from transcript_ledger import (
    append_transcript_event,
    replay_transcript_events,
    verify_mixed_ledger,
)
from transcript_topology import linearize_transcript_topology

RUN_ID = "run_determinism_001"
TS_A = "2026-05-11T09:00:00+00:00"
TS_B = "2026-05-11T09:00:01+00:00"
TS_C = "2026-05-11T09:00:02+00:00"
TS_D = "2026-05-11T09:00:03+00:00"


def _summary_json(summary: dict) -> str:
    return json.dumps(summary, sort_keys=True, separators=(",", ":"))


def _make_critique_exchange():
    proposal = make_transcript_event(
        run_id=RUN_ID, sender="agent_proposer", recipient="broadcast",
        role="proposal", content="Add causal edge: workload -> burnout",
        created_at=TS_A,
    )
    critique_a = make_transcript_event(
        run_id=RUN_ID, sender="agent_critic_a", recipient="agent_proposer",
        role="critique", content="Workload -> burnout lacks longitudinal support",
        created_at=TS_B,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    critique_b = make_transcript_event(
        run_id=RUN_ID, sender="agent_critic_b", recipient="agent_proposer",
        role="critique", content="Alternative pathway is more defensible",
        created_at=TS_C,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    arbiter = make_transcript_event(
        run_id=RUN_ID, sender="agent_arbiter", recipient="broadcast",
        role="arbiter", content="Proposal deferred. Both critiques accepted.",
        created_at=TS_D,
        parent_message_id=critique_a["message_id"],
        references=[critique_a["message_id"], critique_b["message_id"], proposal["message_id"]],
    )
    return proposal, critique_a, critique_b, arbiter


# 1. Repeated pipeline runs produce byte-identical summaries
def test_repeated_pipeline_runs_byte_identical(tmp_path):
    summaries = []
    for i in range(4):
        path = tmp_path / f"ledger_{i}.jsonl"
        summaries.append(_summary_json(run_transcript_critique_loop(path)))
    assert len(set(summaries)) == 1, "Pipeline summaries differ across runs"


# 2. Hash chain is valid across repeated runs (rolling hash is run-specific due to timestamps)
def test_ledger_hash_chain_valid_across_runs(tmp_path):
    # LedgerWriter stamps each event with utc_now(), so rolling hashes differ per run.
    # What must hold: each ledger's chain is internally consistent (ok: True).
    for i in range(3):
        path = tmp_path / f"ledger_{i}.jsonl"
        run_transcript_critique_loop(path)
        result = verify_mixed_ledger(path)
        assert result["ok"] is True, f"Hash chain broken on run {i}: {result['failures']}"
        assert result["count"] == 4


# 3. Critique ordering is identical across repeated runs
def test_critique_ordering_stable_across_runs(tmp_path):
    orderings = []
    for i in range(3):
        path = tmp_path / f"ledger_{i}.jsonl"
        summary = run_transcript_critique_loop(path)
        orderings.append(json.dumps(summary["roles"], separators=(",", ":")))
    assert len(set(orderings)) == 1
    assert json.loads(orderings[0]) == ["proposal", "critique", "critique", "arbiter"]


# 4. Arbitration/replay output is identical across repeated runs
def test_arbitration_output_stable_across_runs(tmp_path):
    replay_orders = []
    for i in range(3):
        path = tmp_path / f"ledger_{i}.jsonl"
        summary = run_transcript_critique_loop(path)
        replay_orders.append(json.dumps(summary["replay_order"], separators=(",", ":")))
    assert len(set(replay_orders)) == 1


# 5. Deterministic sibling ordering survives randomized insertion order
def test_sibling_ordering_survives_randomized_insertion(tmp_path):
    proposal, critique_a, critique_b, arbiter = _make_critique_exchange()
    siblings = [critique_a, critique_b]

    reference_order = None
    rng = random.Random(42)

    for i in range(20):
        path = tmp_path / f"ledger_{i}.jsonl"
        shuffled_siblings = siblings[:]
        rng.shuffle(shuffled_siblings)
        for event in [proposal] + shuffled_siblings + [arbiter]:
            append_transcript_event(event, path)

        raw = replay_transcript_events(path)
        linearized = linearize_transcript_topology(raw)
        order = [e["message_id"] for e in linearized]

        if reference_order is None:
            reference_order = order
        else:
            assert order == reference_order, (
                f"Linearized order differed on shuffle {i}: {order}"
            )

        # Siblings always before arbiter
        arb_pos = order.index(arbiter["message_id"])
        assert order.index(critique_a["message_id"]) < arb_pos
        assert order.index(critique_b["message_id"]) < arb_pos
        # Proposal always first
        assert order[0] == proposal["message_id"]


# 6. Canonical linearized output is byte-identical across shuffles
def test_canonical_output_byte_identical_across_shuffles(tmp_path):
    proposal, critique_a, critique_b, arbiter = _make_critique_exchange()
    events = [proposal, critique_a, critique_b, arbiter]
    rng = random.Random(99)

    outputs = []
    for i in range(10):
        shuffled = events[:]
        rng.shuffle(shuffled)
        linearized = linearize_transcript_topology(shuffled)
        outputs.append(canonical_json(linearized))

    assert len(set(outputs)) == 1, "Canonical output differed across shuffles"


# 7. Replay hash chain valid for all sibling shuffle variants
def test_hash_chain_valid_for_all_shuffle_variants(tmp_path):
    proposal, critique_a, critique_b, arbiter = _make_critique_exchange()
    siblings = [critique_a, critique_b]
    rng = random.Random(7)

    for i in range(5):
        path = tmp_path / f"ledger_{i}.jsonl"
        shuffled_siblings = siblings[:]
        rng.shuffle(shuffled_siblings)
        for event in [proposal] + shuffled_siblings + [arbiter]:
            append_transcript_event(event, path)
        result = verify_mixed_ledger(path)
        assert result["ok"] is True, f"Hash chain broken on shuffle {i}: {result['failures']}"
        assert result["count"] == 4
