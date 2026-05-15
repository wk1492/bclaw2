"""
Deterministic query helpers over a built epistemic graph.

All functions are pure: no I/O, no mutation, no global state.
Input graph must be produced by build_epistemic_graph().
"""
from __future__ import annotations

from typing import Optional

from epistemic_graph import EpistemicEdge, EpistemicNode

_EVIDENCE_RELATIONS = frozenset({"evidence_for", "evidence_against"})


def get_claim(graph: dict, claim_id: str) -> Optional[EpistemicNode]:
    for node in graph.get("nodes", ()):
        if node.claim_id == claim_id:
            return node
    return None


def _nodes_by_ids(graph: dict, ids: set[str]) -> list[EpistemicNode]:
    return sorted(
        (n for n in graph.get("nodes", ()) if n.claim_id in ids),
        key=lambda n: n.claim_id,
    )


def get_supporting_claims(graph: dict, claim_id: str) -> list[EpistemicNode]:
    """Nodes whose edge points TO claim_id with relation 'supports'."""
    ids = {
        e.source for e in graph.get("edges", ())
        if e.target == claim_id and e.relation == "supports"
    }
    return _nodes_by_ids(graph, ids)


def get_attacking_claims(graph: dict, claim_id: str) -> list[EpistemicNode]:
    """Nodes whose edge points TO claim_id with relation 'attacks'."""
    ids = {
        e.source for e in graph.get("edges", ())
        if e.target == claim_id and e.relation == "attacks"
    }
    return _nodes_by_ids(graph, ids)


def get_critiques(graph: dict, claim_id: str) -> list[EpistemicNode]:
    """Nodes whose edge points TO claim_id with relation 'critique_of'."""
    ids = {
        e.source for e in graph.get("edges", ())
        if e.target == claim_id and e.relation == "critique_of"
    }
    return _nodes_by_ids(graph, ids)


def get_evidence_refs(graph: dict, claim_id: str) -> list[EpistemicNode]:
    """Nodes that claim_id cites as evidence (outgoing evidence_for or evidence_against edges)."""
    ids = {
        e.target for e in graph.get("edges", ())
        if e.source == claim_id and e.relation in _EVIDENCE_RELATIONS
    }
    return _nodes_by_ids(graph, ids)


def get_claim_neighborhood(graph: dict, claim_id: str, depth: int = 1) -> dict:
    """
    BFS neighborhood around claim_id up to `depth` hops (traversing all edge directions).

    Returns:
        center      — the central claim_id
        depth       — the requested depth
        claim_ids   — sorted list of all claim_ids in the neighborhood (including center)
        edges       — list of EpistemicEdge objects within the neighborhood
    """
    edges = graph.get("edges", ())

    adj: dict[str, set[str]] = {}
    for e in edges:
        adj.setdefault(e.source, set()).add(e.target)
        adj.setdefault(e.target, set()).add(e.source)

    visited: set[str] = {claim_id}
    frontier = {claim_id}
    for _ in range(depth):
        next_frontier: set[str] = set()
        for nid in frontier:
            for neighbor in adj.get(nid, ()):
                if neighbor not in visited:
                    next_frontier.add(neighbor)
        visited |= next_frontier
        frontier = next_frontier
        if not frontier:
            break

    neighborhood_edges = [
        e for e in edges
        if e.source in visited and e.target in visited
    ]

    return {
        "center": claim_id,
        "depth": depth,
        "claim_ids": sorted(visited),
        "edges": neighborhood_edges,
    }


def claim_status_snapshot(graph: dict) -> dict:
    """
    Extract a flat {claim_id: epistemic_status} snapshot from a built graph.

    Returns a plain dict in sorted claim_id order. Values are str or None.
    Pure function. Graph is never mutated. Safe to diff with diff_epistemic_state.
    """
    return {
        n.claim_id: n.epistemic_status
        for n in sorted(graph.get("nodes", ()), key=lambda n: n.claim_id)
    }


def summarize_graph(graph: dict) -> dict:
    """
    JSON-safe summary of an epistemic graph.

    Returns:
        node_count          — int
        edge_count          — int
        relation_counts     — dict[str, int] sorted by relation name
        dangling_ref_count  — int
        isolated_node_count — int (nodes with no edges)
    """
    nodes = graph.get("nodes", ())
    edges = graph.get("edges", ())

    relation_counts: dict[str, int] = {}
    for e in edges:
        relation_counts[e.relation] = relation_counts.get(e.relation, 0) + 1

    connected: set[str] = set()
    for e in edges:
        connected.add(e.source)
        connected.add(e.target)

    isolated = sum(1 for n in nodes if n.claim_id not in connected)

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "relation_counts": dict(sorted(relation_counts.items())),
        "dangling_ref_count": len(graph.get("dangling_refs", [])),
        "isolated_node_count": isolated,
    }
