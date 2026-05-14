import pytest

from epistemic_event import make_epistemic_event
from epistemic_graph import EpistemicEdge, EpistemicNode, build_epistemic_graph, epistemic_claim_id
from epistemic_graph_queries import (
    get_attacking_claims,
    get_claim,
    get_claim_neighborhood,
    get_critiques,
    get_evidence_refs,
    get_supporting_claims,
    summarize_graph,
)

RUN_ID = "run_query_test"
TS_A = "2026-05-14T10:00:00+00:00"
TS_B = "2026-05-14T10:00:01+00:00"
TS_C = "2026-05-14T10:00:02+00:00"
TS_D = "2026-05-14T10:00:03+00:00"


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


def _supporter(target):
    return make_epistemic_event(
        RUN_ID, "agent_c", "broadcast", "proposal",
        "Supporting evidence", TS_C,
        claim_type="observation", epistemic_status="supported",
        evidence_refs=[target["message_id"]],
    )


def _attacker(target):
    return make_epistemic_event(
        RUN_ID, "agent_d", "broadcast", "proposal",
        "Retraction", TS_D,
        claim_type="retraction",
        evidence_refs=[target["message_id"]],
    )


# ── 1. get_claim ──────────────────────────────────────────────────────────────

def test_get_claim_returns_node():
    p = _proposal()
    g = build_epistemic_graph([p])
    cid = g["nodes"][0].claim_id
    node = get_claim(g, cid)
    assert isinstance(node, EpistemicNode)
    assert node.claim_id == cid


def test_get_claim_missing_returns_none():
    g = build_epistemic_graph([_proposal()])
    assert get_claim(g, "claim_doesnotexist000000") is None


def test_get_claim_empty_graph_returns_none():
    g = build_epistemic_graph([])
    assert get_claim(g, "claim_any") is None


# ── 2. get_supporting_claims ──────────────────────────────────────────────────

def test_get_supporting_claims_returns_supporter():
    p = _proposal()
    s = _supporter(p)
    g = build_epistemic_graph([p, s])
    p_cid = g["nodes"][0].claim_id if g["nodes"][0].claim_type == "assertion" else g["nodes"][1].claim_id
    # find proposal node
    p_node = next(n for n in g["nodes"] if n.claim_type == "assertion")
    supporters = get_supporting_claims(g, p_node.claim_id)
    assert len(supporters) == 1
    assert supporters[0].claim_type == "observation"


def test_get_supporting_claims_empty_when_none():
    p = _proposal()
    g = build_epistemic_graph([p])
    result = get_supporting_claims(g, g["nodes"][0].claim_id)
    assert result == []


# ── 3. get_attacking_claims ───────────────────────────────────────────────────

def test_get_attacking_claims_returns_attacker():
    p = _proposal()
    a = _attacker(p)
    g = build_epistemic_graph([p, a])
    p_node = next(n for n in g["nodes"] if n.claim_type == "assertion")
    attackers = get_attacking_claims(g, p_node.claim_id)
    assert len(attackers) == 1
    assert attackers[0].claim_type == "retraction"


def test_get_attacking_claims_empty_when_none():
    p = _proposal()
    g = build_epistemic_graph([p])
    assert get_attacking_claims(g, g["nodes"][0].claim_id) == []


# ── 4. get_critiques ──────────────────────────────────────────────────────────

def test_get_critiques_returns_critique():
    p = _proposal()
    c = _critique(p)
    g = build_epistemic_graph([p, c])
    p_node = next(n for n in g["nodes"] if n.claim_type == "assertion")
    critiques = get_critiques(g, p_node.claim_id)
    assert len(critiques) == 1
    assert critiques[0].claim_type == "hypothesis"


def test_get_critiques_empty_when_none():
    p = _proposal()
    g = build_epistemic_graph([p])
    assert get_critiques(g, g["nodes"][0].claim_id) == []


# ── 5. get_evidence_refs ──────────────────────────────────────────────────────

def test_get_evidence_refs_returns_cited_nodes():
    p = _proposal()
    # Use a plain evidence_for event (no special role or status override)
    citer = make_epistemic_event(
        RUN_ID, "agent_c", "broadcast", "proposal", "Citing proposal", TS_C,
        claim_type="inference",
        evidence_refs=[p["message_id"]],
    )
    g = build_epistemic_graph([p, citer])
    c_node = next(n for n in g["nodes"] if n.claim_type == "inference")
    refs = get_evidence_refs(g, c_node.claim_id)
    assert len(refs) >= 1
    assert any(n.claim_type == "assertion" for n in refs)


def test_get_evidence_refs_empty_for_root():
    p = _proposal()
    g = build_epistemic_graph([p])
    assert get_evidence_refs(g, g["nodes"][0].claim_id) == []


# ── 6. get_claim_neighborhood ─────────────────────────────────────────────────

def test_neighborhood_depth1_includes_direct_neighbors():
    p = _proposal()
    c = _critique(p)
    g = build_epistemic_graph([p, c])
    p_node = next(n for n in g["nodes"] if n.claim_type == "assertion")
    nbhd = get_claim_neighborhood(g, p_node.claim_id, depth=1)
    assert nbhd["center"] == p_node.claim_id
    assert nbhd["depth"] == 1
    assert len(nbhd["claim_ids"]) == 2
    assert p_node.claim_id in nbhd["claim_ids"]


def test_neighborhood_depth0_contains_only_center():
    p = _proposal()
    c = _critique(p)
    g = build_epistemic_graph([p, c])
    p_node = next(n for n in g["nodes"] if n.claim_type == "assertion")
    nbhd = get_claim_neighborhood(g, p_node.claim_id, depth=0)
    assert nbhd["claim_ids"] == [p_node.claim_id]
    assert nbhd["edges"] == []


def test_neighborhood_edges_are_within_neighborhood():
    p = _proposal()
    c = _critique(p)
    g = build_epistemic_graph([p, c])
    p_node = next(n for n in g["nodes"] if n.claim_type == "assertion")
    nbhd = get_claim_neighborhood(g, p_node.claim_id, depth=1)
    ids = set(nbhd["claim_ids"])
    for edge in nbhd["edges"]:
        assert edge.source in ids
        assert edge.target in ids


# ── 7. summarize_graph ────────────────────────────────────────────────────────

def test_summarize_empty_graph():
    g = build_epistemic_graph([])
    s = summarize_graph(g)
    assert s["node_count"] == 0
    assert s["edge_count"] == 0
    assert s["relation_counts"] == {}
    assert s["dangling_ref_count"] == 0
    assert s["isolated_node_count"] == 0


def test_summarize_single_node_is_isolated():
    p = _proposal()
    g = build_epistemic_graph([p])
    s = summarize_graph(g)
    assert s["node_count"] == 1
    assert s["edge_count"] == 0
    assert s["isolated_node_count"] == 1


def test_summarize_relation_counts_correct():
    p = _proposal()
    c = _critique(p)
    g = build_epistemic_graph([p, c])
    s = summarize_graph(g)
    assert s["node_count"] == 2
    assert s["edge_count"] == g["edge_count"]
    total = sum(s["relation_counts"].values())
    assert total == s["edge_count"]


def test_summarize_is_json_safe():
    import json
    p = _proposal()
    c = _critique(p)
    g = build_epistemic_graph([p, c])
    s = summarize_graph(g)
    serialized = json.dumps(s)
    assert isinstance(serialized, str)


def test_summarize_dangling_ref_count():
    p = make_epistemic_event(
        RUN_ID, "agent_a", "broadcast", "proposal", "Dangling test", TS_A,
        claim_type="assertion",
        evidence_refs=["tmsg_nonexistent000000000000"],
    )
    g = build_epistemic_graph([p])
    s = summarize_graph(g)
    assert s["dangling_ref_count"] == 1
