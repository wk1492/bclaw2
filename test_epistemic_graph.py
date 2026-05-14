import json

from epistemic_event import epistemic_claim_id, make_epistemic_event
from epistemic_graph import derive_epistemic_graph
from transcript_event import canonical_json, make_transcript_event
from transcript_ledger import append_transcript_event, replay_transcript_events

RUN_ID = "run_graph_test"
TS_A = "2026-05-14T10:00:00+00:00"
TS_B = "2026-05-14T10:00:01+00:00"
TS_C = "2026-05-14T10:00:02+00:00"


def _proposal():
    return make_epistemic_event(
        RUN_ID, "agent_a", "broadcast", "proposal",
        "Add causal edge: fatigue -> error_rate", TS_A,
        claim_type="assertion", epistemic_status="proposed", confidence=0.7,
    )


def _critique(proposal):
    return make_epistemic_event(
        RUN_ID, "agent_b", "agent_a", "critique",
        "Edge weight unsubstantiated", TS_B,
        claim_type="hypothesis", epistemic_status="contested",
        evidence_refs=[proposal["message_id"]],
    )


def _plain():
    return make_transcript_event(
        RUN_ID, "agent_c", "broadcast", "arbiter", "Plain arbiter", TS_C,
    )


# 1. Empty event list returns empty graph
def test_empty_events_returns_empty_graph():
    g = derive_epistemic_graph([])
    assert g["nodes"] == {}
    assert g["edges"] == []
    assert g["node_count"] == 0
    assert g["edge_count"] == 0
    assert g["dangling_refs"] == []


# 2. Non-epistemic transcript events are ignored
def test_non_epistemic_events_ignored():
    g = derive_epistemic_graph([_plain()])
    assert g["node_count"] == 0
    assert g["edge_count"] == 0


# 3. Epistemic claim becomes a deterministic node
def test_epistemic_claim_becomes_node():
    p = _proposal()
    g = derive_epistemic_graph([p])
    assert g["node_count"] == 1
    cid = epistemic_claim_id(p)
    assert cid in g["nodes"]
    node = g["nodes"][cid]
    assert node["claim_type"] == "assertion"
    assert node["epistemic_status"] == "proposed"
    assert node["confidence"] == 0.7
    assert node["sender"] == "agent_a"


# 4. evidence_refs create deterministic edges
def test_evidence_refs_create_edges():
    p = _proposal()
    c = _critique(p)
    g = derive_epistemic_graph([p, c])
    assert g["edge_count"] == 1
    edge = g["edges"][0]
    assert edge["source"] == epistemic_claim_id(c)
    assert edge["target"] == epistemic_claim_id(p)
    assert edge["relation"] == "evidence"


# 5. Repeated graph derivation is byte-identical
def test_repeated_derivation_byte_identical():
    p = _proposal()
    c = _critique(p)
    events = [p, c]
    results = [canonical_json(derive_epistemic_graph(events)) for _ in range(5)]
    assert len(set(results)) == 1


# 6. Input events are not mutated
def test_input_events_not_mutated():
    p = _proposal()
    c = _critique(p)
    original_keys_p = set(p.keys())
    original_keys_c = set(c.keys())
    derive_epistemic_graph([p, c])
    assert set(p.keys()) == original_keys_p
    assert set(c.keys()) == original_keys_c


# 7. Graph can be reconstructed from ledger replay only
def test_reconstruct_from_ledger_only(tmp_path):
    path = tmp_path / "ledger.jsonl"
    p = _proposal()
    c = _critique(p)

    # Expected graph derived before appending (clean pre-decoration events)
    expected = derive_epistemic_graph([p, c])

    append_transcript_event(p, path)
    append_transcript_event(c, path)
    del p, c  # discard in-memory objects

    replayed = replay_transcript_events(path)
    reconstructed = derive_epistemic_graph(replayed)

    # node_count, edge_count, dangling_refs must match
    assert reconstructed["node_count"] == expected["node_count"]
    assert reconstructed["edge_count"] == expected["edge_count"]
    assert reconstructed["dangling_refs"] == expected["dangling_refs"]
    # Node IDs and edge endpoints must be identical
    assert set(reconstructed["nodes"].keys()) == set(expected["nodes"].keys())
    assert canonical_json(reconstructed["edges"]) == canonical_json(expected["edges"])


# 8. epistemic_claim_id is used as node identity (claim_ prefix, 30 chars)
def test_node_identity_uses_epistemic_claim_id():
    p = _proposal()
    g = derive_epistemic_graph([p])
    for node_id in g["nodes"]:
        assert node_id.startswith("claim_")
        assert len(node_id) == 30


# 9. Mixed epistemic and non-epistemic events — only epistemic become nodes
def test_mixed_events_only_epistemic_nodes():
    p = _proposal()
    plain = _plain()
    g = derive_epistemic_graph([p, plain])
    assert g["node_count"] == 1
    assert g["edge_count"] == 0


# 10. Dangling refs detected when evidence_ref doesn't resolve to a known node
def test_dangling_refs_detected():
    p = make_epistemic_event(
        RUN_ID, "agent_a", "broadcast", "proposal", "Dangling test", TS_A,
        claim_type="assertion",
        evidence_refs=["tmsg_nonexistent000000000000"],
    )
    g = derive_epistemic_graph([p])
    assert "tmsg_nonexistent000000000000" in g["dangling_refs"]
    assert g["edge_count"] == 0


# 11. Multiple events — correct node and edge counts
def test_multiple_events_correct_counts():
    p = _proposal()
    c1 = _critique(p)
    c2 = make_epistemic_event(
        RUN_ID, "agent_c", "agent_a", "critique", "Another critique", TS_C,
        claim_type="inference", epistemic_status="proposed",
        evidence_refs=[p["message_id"]],
    )
    g = derive_epistemic_graph([p, c1, c2])
    assert g["node_count"] == 3
    assert g["edge_count"] == 2


# 12. Two independent runs from same input produce identical canonical JSON
def test_two_runs_canonical_identical():
    p = _proposal()
    c = _critique(p)
    g1 = derive_epistemic_graph([p, c])
    g2 = derive_epistemic_graph([p, c])
    assert canonical_json(g1) == canonical_json(g2)


# 13. Edges are sorted deterministically regardless of event insertion order
def test_edges_sorted_deterministically():
    p = _proposal()
    c = _critique(p)
    g_forward = derive_epistemic_graph([p, c])
    g_reversed = derive_epistemic_graph([c, p])
    assert canonical_json(g_forward["edges"]) == canonical_json(g_reversed["edges"])


# 14. Node values include all expected keys
def test_node_values_have_expected_keys():
    p = _proposal()
    g = derive_epistemic_graph([p])
    cid = next(iter(g["nodes"]))
    node = g["nodes"][cid]
    for key in ("claim_id", "message_id", "claim_type", "epistemic_status",
                "confidence", "sender", "role"):
        assert key in node
