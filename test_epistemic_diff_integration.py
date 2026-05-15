"""
Integration probe: diff_epistemic_state composed with claim_status_snapshot.

Verifies that epistemic_diff can be safely composed with the epistemic graph
query layer as a pure observer. No ledger writes. No replay mutation. No state
mutation. No orchestration coupling.
"""
import copy
import json

from epistemic_event import make_epistemic_event
from epistemic_graph import build_epistemic_graph
from epistemic_graph_queries import claim_status_snapshot
from epistemic_diff import diff_epistemic_state

RUN_ID = "run_integration_probe"
TS_A = "2026-05-14T10:00:00+00:00"
TS_B = "2026-05-14T10:00:01+00:00"
TS_C = "2026-05-14T10:00:02+00:00"


def _graph_v1():
    proposal = make_epistemic_event(
        RUN_ID, "agent_a", "broadcast", "proposal",
        "Initial causal claim", TS_A,
        claim_type="assertion", epistemic_status="proposed",
    )
    return build_epistemic_graph([proposal])


def _graph_v2():
    proposal = make_epistemic_event(
        RUN_ID, "agent_a", "broadcast", "proposal",
        "Initial causal claim", TS_A,
        claim_type="assertion", epistemic_status="proposed",
    )
    supporter = make_epistemic_event(
        RUN_ID, "agent_b", "broadcast", "proposal",
        "Supporting observation", TS_B,
        claim_type="observation", epistemic_status="supported",
        evidence_refs=[proposal["message_id"]],
    )
    return build_epistemic_graph([proposal, supporter])


# ── Deterministic output ──────────────────────────────────────────────────────

def test_diff_of_graph_snapshots_is_deterministic():
    g1 = _graph_v1()
    g2 = _graph_v2()
    snap1 = claim_status_snapshot(g1)
    snap2 = claim_status_snapshot(g2)
    opts = dict(sort_keys=True, separators=(",", ":"))
    r1 = json.dumps(diff_epistemic_state(snap1, snap2), **opts)
    r2 = json.dumps(diff_epistemic_state(snap1, snap2), **opts)
    assert r1 == r2


# ── No behavior mutation ──────────────────────────────────────────────────────

def test_diff_does_not_mutate_graph_snapshots():
    g1 = _graph_v1()
    g2 = _graph_v2()
    snap1 = claim_status_snapshot(g1)
    snap2 = claim_status_snapshot(g2)
    snap1_copy = copy.deepcopy(snap1)
    snap2_copy = copy.deepcopy(snap2)
    diff_epistemic_state(snap1, snap2)
    assert snap1 == snap1_copy
    assert snap2 == snap2_copy


# ── No replay mutation ────────────────────────────────────────────────────────

def test_diff_does_not_mutate_source_graphs():
    g1 = _graph_v1()
    g2 = _graph_v2()
    node_ids_before = {n.claim_id for n in g1["nodes"]}
    edge_count_before = g1["edge_count"]
    snap1 = claim_status_snapshot(g1)
    snap2 = claim_status_snapshot(g2)
    diff_epistemic_state(snap1, snap2)
    assert {n.claim_id for n in g1["nodes"]} == node_ids_before
    assert g1["edge_count"] == edge_count_before


# ── Correct diff semantics ────────────────────────────────────────────────────

def test_added_claim_appears_in_diff():
    g1 = _graph_v1()
    g2 = _graph_v2()
    result = diff_epistemic_state(claim_status_snapshot(g1), claim_status_snapshot(g2))
    assert len(result["added"]) == 1
    assert result["removed"] == {}
    added_status = next(iter(result["added"].values()))
    assert added_status == "supported"


def test_snapshot_of_identical_graphs_produces_no_diff():
    g1 = _graph_v1()
    g1_again = _graph_v1()
    result = diff_epistemic_state(
        claim_status_snapshot(g1),
        claim_status_snapshot(g1_again),
    )
    assert result == {"added": {}, "removed": {}, "changed": {}}


# ── claim_status_snapshot contract ───────────────────────────────────────────

def test_claim_status_snapshot_returns_sorted_dict():
    g2 = _graph_v2()
    snap = claim_status_snapshot(g2)
    assert list(snap.keys()) == sorted(snap.keys())


def test_claim_status_snapshot_does_not_mutate_graph():
    g1 = _graph_v1()
    node_count_before = g1["node_count"]
    claim_status_snapshot(g1)
    assert g1["node_count"] == node_count_before
    assert len(g1["nodes"]) == node_count_before
