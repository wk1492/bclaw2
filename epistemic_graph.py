"""
Deterministic epistemic graph topology layer.

Pure functions only. No I/O. No caches. No global state. No mutation of inputs.

Claim IDs are stable across ledger round-trips: decoration fields added by
LedgerWriter (timestamp, event_hash, event_id, rolling_hash, previous_hash)
are stripped before computing node identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from epistemic_event import EPISTEMIC_FIELDS, epistemic_claim_id

_DECORATION_FIELDS = frozenset({
    "timestamp", "event_hash", "event_id", "rolling_hash", "previous_hash",
})

VALID_RELATIONS = frozenset({
    "parent_claim_id",
    "evidence_for",
    "evidence_against",
    "critique_of",
    "supports",
    "attacks",
})


@dataclass(frozen=True)
class EpistemicNode:
    claim_id: str
    message_id: str
    claim_type: Optional[str] = None
    epistemic_status: Optional[str] = None
    confidence: Optional[float] = None
    sender: Optional[str] = None
    role: Optional[str] = None


@dataclass(frozen=True)
class EpistemicEdge:
    source: str   # claim_id
    target: str   # claim_id
    relation: str  # member of VALID_RELATIONS


def _is_epistemic(event: dict) -> bool:
    return bool(EPISTEMIC_FIELDS & set(event.keys()))


def _stable_id(event: dict) -> str:
    """Claim ID stable across ledger round-trips (decoration fields excluded)."""
    return epistemic_claim_id(
        {k: v for k, v in event.items() if k not in _DECORATION_FIELDS}
    )


def _infer_relation(event: dict) -> str:
    """Infer evidence_refs edge relation from event fields."""
    if event.get("claim_type") == "retraction":
        return "attacks"
    if event.get("role") == "critique":
        return "critique_of"
    if event.get("epistemic_status") == "supported":
        return "supports"
    if event.get("epistemic_status") in ("refuted", "contested"):
        return "evidence_against"
    return "evidence_for"


def build_epistemic_graph(events: list) -> dict:
    """
    Build a deterministic epistemic graph from replayed transcript events.

    Non-epistemic events (no EPISTEMIC_FIELDS keys present) are silently ignored.
    Input list and event dicts are never mutated.

    Returns a dict with:
        nodes         — sorted tuple[EpistemicNode]
        edges         — sorted tuple[EpistemicEdge]
        node_count    — int
        edge_count    — int
        dangling_refs — sorted list[str] of refs resolving to no known node
    """
    epistemic = [e for e in events if _is_epistemic(e)]

    nodes: dict[str, EpistemicNode] = {}
    msg_to_cid: dict[str, str] = {}
    for e in epistemic:
        cid = _stable_id(e)
        nodes[cid] = EpistemicNode(
            claim_id=cid,
            message_id=e["message_id"],
            claim_type=e.get("claim_type"),
            epistemic_status=e.get("epistemic_status"),
            confidence=e.get("confidence"),
            sender=e.get("sender"),
            role=e.get("role"),
        )
        msg_to_cid[e["message_id"]] = cid

    edges: list[EpistemicEdge] = []
    dangling: set[str] = set()

    for e in epistemic:
        source = _stable_id(e)

        # parent_message_id → parent_claim_id edge
        pid = e.get("parent_message_id")
        if pid is not None:
            if pid in msg_to_cid:
                edges.append(EpistemicEdge(
                    source=source, target=msg_to_cid[pid],
                    relation="parent_claim_id",
                ))
            else:
                dangling.add(pid)

        # evidence_refs → typed edges
        relation = _infer_relation(e)
        for ref in e.get("evidence_refs", []):
            if ref in msg_to_cid:
                edges.append(EpistemicEdge(
                    source=source, target=msg_to_cid[ref], relation=relation,
                ))
            else:
                dangling.add(ref)

    sorted_nodes = tuple(sorted(nodes.values(), key=lambda n: n.claim_id))
    sorted_edges = tuple(sorted(
        edges, key=lambda x: (x.source, x.target, x.relation)
    ))

    return {
        "nodes": sorted_nodes,
        "edges": sorted_edges,
        "node_count": len(sorted_nodes),
        "edge_count": len(sorted_edges),
        "dangling_refs": sorted(dangling),
    }


def validate_epistemic_graph(graph: dict) -> list[str]:
    """
    Validate an epistemic graph for structural integrity.

    Returns a list of error strings. Empty list means valid.
    Checks: duplicate IDs, dangling edge endpoints, self-references, invalid relations.
    """
    errors: list[str] = []
    nodes = graph.get("nodes", ())
    edges = graph.get("edges", ())

    seen: set[str] = set()
    for node in nodes:
        if node.claim_id in seen:
            errors.append(f"duplicate node ID: {node.claim_id}")
        seen.add(node.claim_id)

    node_ids = {n.claim_id for n in nodes}

    for edge in edges:
        if edge.source not in node_ids:
            errors.append(f"dangling edge source: {edge.source}")
        if edge.target not in node_ids:
            errors.append(f"dangling edge target: {edge.target}")
        if edge.source == edge.target:
            errors.append(f"illegal self-reference: {edge.source}")
        if edge.relation not in VALID_RELATIONS:
            errors.append(f"invalid relation: {edge.relation!r}")

    return errors


def detect_cycles(graph: dict) -> list[str]:
    """
    Detect cycles in the epistemic graph using iterative DFS.

    Returns sorted list of claim_ids involved in cycles.
    Empty list means acyclic.
    """
    nodes = {n.claim_id for n in graph.get("nodes", ())}
    edges = graph.get("edges", ())

    adj: dict[str, list[str]] = {nid: [] for nid in nodes}
    for edge in edges:
        if edge.source in nodes and edge.target in nodes:
            adj[edge.source].append(edge.target)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {nid: WHITE for nid in nodes}
    cycle_nodes: set[str] = set()

    def _dfs(start: str) -> None:
        stack = [(start, iter(sorted(adj[start])))]
        path: list[str] = [start]
        path_set: set[str] = {start}
        color[start] = GRAY

        while stack:
            nid, neighbors = stack[-1]
            try:
                neighbor = next(neighbors)
                if color.get(neighbor) == GRAY:
                    # Back edge — collect cycle nodes from path
                    idx = path.index(neighbor)
                    for cn in path[idx:]:
                        cycle_nodes.add(cn)
                elif color.get(neighbor) == WHITE:
                    color[neighbor] = GRAY
                    path.append(neighbor)
                    path_set.add(neighbor)
                    stack.append((neighbor, iter(sorted(adj[neighbor]))))
            except StopIteration:
                color[nid] = BLACK
                path.pop()
                path_set.discard(nid)
                stack.pop()

    for nid in sorted(nodes):
        if color[nid] == WHITE:
            _dfs(nid)

    return sorted(cycle_nodes)


def topological_claim_order(graph: dict) -> list[str]:
    """
    Return claim_ids in topological order using Kahn's algorithm.

    Tie-break: alphabetical by claim_id (deterministic).
    Raises ValueError if the graph contains cycles.
    Returns empty list for empty graph.
    """
    nodes = {n.claim_id for n in graph.get("nodes", ())}
    edges = graph.get("edges", ())

    if not nodes:
        return []

    # Edge source→target means "source depends on target" (target is the ancestor).
    # For topological order (ancestors first): when target is processed, source can proceed.
    in_degree: dict[str, int] = {nid: 0 for nid in nodes}
    adj: dict[str, list[str]] = {nid: [] for nid in nodes}  # adj[x] = nodes that depend on x

    for edge in edges:
        if edge.source in nodes and edge.target in nodes:
            adj[edge.target].append(edge.source)  # target unlocks source
            in_degree[edge.source] += 1           # source waits for target

    ready = sorted(nid for nid, deg in in_degree.items() if deg == 0)
    result: list[str] = []

    while ready:
        chosen = ready.pop(0)
        result.append(chosen)
        newly_ready = []
        for dependent in sorted(adj[chosen]):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                newly_ready.append(dependent)
        ready = sorted(ready + newly_ready)

    if len(result) != len(nodes):
        raise ValueError(
            f"topological_claim_order: cycle detected — "
            f"{len(nodes) - len(result)} node(s) could not be ordered"
        )

    return result
