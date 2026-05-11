"""
Deterministic FCM graph apply layer.

Pure function: validated dry-run plans + optional baseline snapshot
→ deterministic applied graph object.

No model calls. No persistence. No mutation of inputs.
No learning. No dynamics propagation. No autonomous arbitration.
"""
import hashlib
import json

from graph_state import Edge, GraphState, Node, make_graph

VALID_SNAPSHOT_STATUSES = {"simulated", "baseline"}
REQUIRED_EDGE_FIELDS = {"edge_id", "source", "target", "weight"}
REQUIRED_PLAN_FIELDS = {"plan_id", "edges", "nodes"}


class GraphApplyError(ValueError):
    pass


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_snapshot(snapshot: dict):
    if snapshot is None:
        return
    status = snapshot.get("status")
    if status not in VALID_SNAPSHOT_STATUSES:
        raise GraphApplyError(
            f"Invalid snapshot status: {status!r}. "
            f"Must be one of {sorted(VALID_SNAPSHOT_STATUSES)}."
        )


def _validate_plan(plan: dict):
    missing = REQUIRED_PLAN_FIELDS - set(plan)
    if missing:
        raise GraphApplyError(f"Plan missing required fields: {sorted(missing)}")
    for edge in plan.get("edges", []):
        if not isinstance(edge, dict):
            raise GraphApplyError(f"Edge must be a dict, got {type(edge)}")
        missing_edge = REQUIRED_EDGE_FIELDS - set(edge)
        if missing_edge:
            raise GraphApplyError(f"Edge missing required fields: {sorted(missing_edge)}")


def _node_from_dict(n: dict) -> Node:
    return Node(
        node_id=n["node_id"],
        label=n.get("label", n["node_id"]),
        activation=float(n.get("activation", 0.0)),
        metadata=n.get("metadata", {}),
    )


def _edge_from_dict(e: dict) -> Edge:
    return Edge(
        edge_id=e["edge_id"],
        source=e["source"],
        target=e["target"],
        weight=float(e["weight"]),
        confidence=float(e.get("confidence", 1.0)),
        edge_type=e.get("edge_type", "causal"),
        metadata=e.get("metadata", {}),
    )


def apply_fcm_plans(
    plans: list,
    baseline_snapshot: dict = None,
    simulated_snapshot: dict = None,
) -> dict:
    """
    Apply validated dry-run plans to produce a deterministic applied graph.

    Args:
        plans: list of validated dry-run plan dicts (each with plan_id, nodes, edges)
        baseline_snapshot: optional immutable baseline graph snapshot dict
        simulated_snapshot: optional simulated snapshot dict (status must be "simulated")

    Returns:
        Deterministic applied graph dict with status="applied".
    """
    # Validate snapshots
    _validate_snapshot(baseline_snapshot)
    _validate_snapshot(simulated_snapshot)

    # Validate plans and check for duplicate plan_ids
    seen_plan_ids: set[str] = set()
    for plan in plans:
        _validate_plan(plan)
        pid = plan["plan_id"]
        if pid in seen_plan_ids:
            raise GraphApplyError(f"Duplicate plan_id: {pid!r}")
        seen_plan_ids.add(pid)

    # Collect nodes and edges from all plans — canonical merge by ID
    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}

    # Start from baseline snapshot if provided
    if baseline_snapshot:
        for n in baseline_snapshot.get("nodes", []):
            nodes[n["node_id"]] = dict(n)
        for e in baseline_snapshot.get("edges", []):
            edges[e["edge_id"]] = dict(e)

    # Overlay simulated snapshot if provided
    if simulated_snapshot:
        for n in simulated_snapshot.get("nodes", []):
            nodes[n["node_id"]] = dict(n)
        for e in simulated_snapshot.get("edges", []):
            edges[e["edge_id"]] = dict(e)

    # Apply plans (plans cannot invent — they can only specify edges/nodes)
    for plan in plans:
        for n in plan.get("nodes", []):
            nodes[n["node_id"]] = dict(n)
        for e in plan.get("edges", []):
            edges[e["edge_id"]] = dict(e)

    # Deterministic canonical ordering
    sorted_nodes = sorted(nodes.values(), key=lambda n: n["node_id"])
    sorted_edges = sorted(
        edges.values(),
        key=lambda e: (e["source"], e["target"], e.get("edge_type", "causal"), e["edge_id"]),
    )
    applied_plan_ids = sorted(seen_plan_ids)
    source_snapshot_id = (
        simulated_snapshot.get("snapshot_id") if simulated_snapshot
        else (baseline_snapshot.get("snapshot_id") if baseline_snapshot else None)
    )

    # Derive graph_id from canonical applied content
    content_for_id = {
        "applied_plan_ids": applied_plan_ids,
        "edges": sorted_edges,
        "nodes": sorted_nodes,
        "source_snapshot_id": source_snapshot_id,
    }
    graph_id = "fcm_applied_" + _sha256(_canonical(content_for_id))[:24]

    return {
        "graph_id": graph_id,
        "nodes": sorted_nodes,
        "edges": sorted_edges,
        "applied_plan_ids": applied_plan_ids,
        "source_snapshot_id": source_snapshot_id,
        "node_count": len(sorted_nodes),
        "edge_count": len(sorted_edges),
        "status": "applied",
    }
