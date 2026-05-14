import pytest

from epistemic_event import epistemic_claim_id, make_epistemic_event
from epistemic_graph import (
    EpistemicEdge,
    EpistemicNode,
    VALID_RELATIONS,
    build_epistemic_graph,
    detect_cycles,
    topological_claim_order,
    validate_epistemic_graph,
)
from transcript_event import make_transcript_event
from transcript_ledger import append_transcript_event, replay_transcript_events

RUN_ID = "run_graph_test"
TS_A = "2026-05-14T10:00:00+00:00"
TS_B = "2026-05-14T10:00:01+00:00"
TS_C = "2026-05-14T10:00:02+00:00"
TS_D = "2026-05-14T10:00:03+00:00"


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _proposal():
    return make_epistemic_event(
        RUN_ID, "agent_a", "broadcast", "proposal",
        "Add causal edge: fatigue -> error_rate", TS_A,
        claim_type="assertion", epistemic_status="proposed", confidence=0.7,
    )


def _critique(parent):
    return make_epistemic_event(
        RUN_ID, "agent_b", "agent_a", "critique",
        "Edge weight unsubstantiated", TS_B,
        claim_type="hypothesis", epistemic_status="contested",
        parent_message_id=parent["message_id"],
        evidence_refs=[parent["message_id"]],
    )


def _plain():
    return make_transcript_event(
        RUN_ID, "agent_c", "broadcast", "arbiter", "Plain arbiter", TS_C,
    )


# ── 1. Valid graph ────────────────────────────────────────────────────────────

def test_valid_graph_passes_validation():
    p = _proposal()
    c = _critique(p)
    g = build_epistemic_graph([p, c])
    errors = validate_epistemic_graph(g)
    assert errors == [], f"unexpected errors: {errors}"


def test_empty_graph_is_valid():
    g = build_epistemic_graph([])
    assert g["node_count"] == 0
    assert g["edge_count"] == 0
    assert validate_epistemic_graph(g) == []
    assert topological_claim_order(g) == []
    assert detect_cycles(g) == []


def test_non_epistemic_events_ignored():
    g = build_epistemic_graph([_plain()])
    assert g["node_count"] == 0


def test_epistemic_node_fields():
    p = _proposal()
    g = build_epistemic_graph([p])
    assert g["node_count"] == 1
    node = g["nodes"][0]
    assert isinstance(node, EpistemicNode)
    assert node.claim_id.startswith("claim_")
    assert node.claim_type == "assertion"
    assert node.epistemic_status == "proposed"
    assert node.confidence == 0.7
    assert node.sender == "agent_a"


# ── 2. Critique chain ─────────────────────────────────────────────────────────

def test_critique_chain_edges():
    p = _proposal()
    c = _critique(p)
    g = build_epistemic_graph([p, c])
    relations = {e.relation for e in g["edges"]}
    assert "critique_of" in relations
    assert "parent_claim_id" in relations


def test_critique_chain_topology():
    p = _proposal()
    c = _critique(p)
    g = build_epistemic_graph([p, c])
    order = topological_claim_order(g)
    proposal_cid = epistemic_claim_id(p)
    critique_cid = epistemic_claim_id(c)
    assert proposal_cid in order
    assert critique_cid in order
    # proposal must come before critique in topological order
    assert order.index(proposal_cid) < order.index(critique_cid)


def test_critique_edges_are_epistemic_edges():
    p = _proposal()
    c = _critique(p)
    g = build_epistemic_graph([p, c])
    for edge in g["edges"]:
        assert isinstance(edge, EpistemicEdge)
        assert edge.relation in VALID_RELATIONS


# ── 3. Support/attack edges ───────────────────────────────────────────────────

def test_support_edges_created_from_supported_status():
    p = _proposal()
    supporter = make_epistemic_event(
        RUN_ID, "agent_c", "broadcast", "proposal", "Supporting evidence", TS_C,
        claim_type="observation", epistemic_status="supported",
        evidence_refs=[p["message_id"]],
    )
    g = build_epistemic_graph([p, supporter])
    relations = {e.relation for e in g["edges"]}
    assert "supports" in relations


def test_attack_edges_created_from_retraction():
    p = _proposal()
    attacker = make_epistemic_event(
        RUN_ID, "agent_d", "broadcast", "proposal", "Retraction attack", TS_D,
        claim_type="retraction",
        evidence_refs=[p["message_id"]],
    )
    g = build_epistemic_graph([p, attacker])
    relations = {e.relation for e in g["edges"]}
    assert "attacks" in relations


def test_evidence_against_from_contested_hypothesis():
    p = _proposal()
    counter = make_epistemic_event(
        RUN_ID, "agent_e", "broadcast", "proposal", "Counter-evidence", TS_B,
        claim_type="hypothesis", epistemic_status="contested",
        evidence_refs=[p["message_id"]],
    )
    g = build_epistemic_graph([p, counter])
    relations = {e.relation for e in g["edges"]}
    assert "evidence_against" in relations


# ── 4. Dangling references fail validation ────────────────────────────────────

def test_dangling_evidence_ref_reported():
    p = make_epistemic_event(
        RUN_ID, "agent_a", "broadcast", "proposal", "Dangling test", TS_A,
        claim_type="assertion",
        evidence_refs=["tmsg_nonexistent000000000000"],
    )
    g = build_epistemic_graph([p])
    assert "tmsg_nonexistent000000000000" in g["dangling_refs"]
    assert g["edge_count"] == 0


def test_dangling_parent_reported():
    p = make_epistemic_event(
        RUN_ID, "agent_a", "broadcast", "proposal", "Orphan", TS_A,
        claim_type="assertion",
        parent_message_id="tmsg_nonexistent000000000000",
    )
    g = build_epistemic_graph([p])
    assert "tmsg_nonexistent000000000000" in g["dangling_refs"]


# ── 5. Self-reference fails validation ───────────────────────────────────────

def test_self_reference_detected_by_validate():
    p = _proposal()
    g = build_epistemic_graph([p])
    # Inject a self-loop manually
    self_edge = EpistemicEdge(
        source=g["nodes"][0].claim_id,
        target=g["nodes"][0].claim_id,
        relation="evidence_for",
    )
    tampered = {**g, "edges": g["edges"] + (self_edge,)}
    errors = validate_epistemic_graph(tampered)
    assert any("self-reference" in e for e in errors)


# ── 6. Cycle detection ────────────────────────────────────────────────────────

def test_acyclic_graph_has_no_cycles():
    p = _proposal()
    c = _critique(p)
    g = build_epistemic_graph([p, c])
    assert detect_cycles(g) == []


def test_cycle_detected_in_cyclic_graph():
    p = _proposal()
    c = _critique(p)
    g = build_epistemic_graph([p, c])
    # Inject a back edge from proposal → critique to create a cycle
    back_edge = EpistemicEdge(
        source=epistemic_claim_id(p),
        target=epistemic_claim_id(c),
        relation="evidence_for",
    )
    cyclic = {**g, "edges": g["edges"] + (back_edge,)}
    cycles = detect_cycles(cyclic)
    assert len(cycles) > 0


def test_topological_order_raises_on_cycle():
    p = _proposal()
    c = _critique(p)
    g = build_epistemic_graph([p, c])
    back_edge = EpistemicEdge(
        source=epistemic_claim_id(p),
        target=epistemic_claim_id(c),
        relation="evidence_for",
    )
    cyclic = {**g, "edges": g["edges"] + (back_edge,)}
    with pytest.raises(ValueError, match="cycle"):
        topological_claim_order(cyclic)


# ── 7. Deterministic ordering ─────────────────────────────────────────────────

def test_topological_order_is_deterministic():
    p = _proposal()
    c = _critique(p)
    g = build_epistemic_graph([p, c])
    orders = [topological_claim_order(g) for _ in range(5)]
    assert len(set(tuple(o) for o in orders)) == 1


def test_node_sort_is_deterministic():
    p = _proposal()
    c = _critique(p)
    g_fwd = build_epistemic_graph([p, c])
    g_rev = build_epistemic_graph([c, p])
    assert [n.claim_id for n in g_fwd["nodes"]] == [n.claim_id for n in g_rev["nodes"]]
    assert g_fwd["edge_count"] == g_rev["edge_count"]


def test_graph_reconstruction_from_ledger_only(tmp_path):
    path = tmp_path / "ledger.jsonl"
    p = _proposal()
    c = _critique(p)
    expected = build_epistemic_graph([p, c])
    append_transcript_event(p, path)
    append_transcript_event(c, path)
    del p, c

    replayed = replay_transcript_events(path)
    reconstructed = build_epistemic_graph(replayed)

    assert reconstructed["node_count"] == expected["node_count"]
    assert reconstructed["edge_count"] == expected["edge_count"]
    assert {n.claim_id for n in reconstructed["nodes"]} == \
           {n.claim_id for n in expected["nodes"]}
    assert reconstructed["dangling_refs"] == expected["dangling_refs"]
