"""
Deterministic FCM dynamics preview layer.

Pure function: applied graph + initial activations → one-step preview.
No mutation. No learning. No persistence. No randomness.
"""
import hashlib
import json


class DynamicsPreviewError(ValueError):
    pass


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def preview_fcm_dynamics(applied_graph: dict, initial_activations: dict) -> dict:
    """
    Compute one deterministic FCM activation update from an applied graph.

    Args:
        applied_graph: output of apply_fcm_plans() — must have status="applied"
        initial_activations: dict mapping node_id -> float activation in [-1.0, 1.0]

    Returns:
        JSON-safe preview dict with status="preview".
        Inputs are not mutated.
    """
    if applied_graph.get("status") != "applied":
        raise DynamicsPreviewError(
            f"Graph status must be 'applied', got {applied_graph.get('status')!r}"
        )

    nodes = applied_graph.get("nodes", [])
    edges = applied_graph.get("edges", [])
    source_graph_id = applied_graph.get("graph_id", "")

    # Validate activation values
    for node_id, val in initial_activations.items():
        if not isinstance(val, (int, float)):
            raise DynamicsPreviewError(
                f"Activation for {node_id!r} must be numeric, got {type(val).__name__}"
            )
        if not (-1.0 <= float(val) <= 1.0):
            raise DynamicsPreviewError(
                f"Activation for {node_id!r} out of range [-1.0, 1.0]: {val}"
            )

    # Validate edge weights
    for edge in edges:
        w = edge.get("weight")
        if not isinstance(w, (int, float)):
            raise DynamicsPreviewError(
                f"Edge {edge.get('edge_id')!r} weight must be numeric, got {type(w).__name__}"
            )
        if not (-1.0 <= float(w) <= 1.0):
            raise DynamicsPreviewError(
                f"Edge {edge.get('edge_id')!r} weight out of range [-1.0, 1.0]: {w}"
            )

    # Build complete node set from graph (missing nodes default to 0.0)
    all_node_ids = sorted(n["node_id"] for n in nodes)
    activations = {nid: 0.0 for nid in all_node_ids}
    for nid, val in initial_activations.items():
        if nid in activations:
            activations[nid] = float(val)

    # Compute one-step update: accumulate incoming edge contributions
    # Nodes with no incoming edges retain their current activation
    has_incoming = {nid: False for nid in all_node_ids}
    delta = {nid: 0.0 for nid in all_node_ids}

    for edge in sorted(edges, key=lambda e: (e["source"], e["target"], e.get("edge_type", ""), e["edge_id"])):
        src = edge["source"]
        tgt = edge["target"]
        if src not in activations or tgt not in activations:
            continue
        delta[tgt] += activations[src] * float(edge["weight"])
        has_incoming[tgt] = True

    updated = {}
    for nid in all_node_ids:
        if has_incoming[nid]:
            updated[nid] = _clamp(delta[nid])
        else:
            updated[nid] = activations[nid]

    # Canonical output structures
    applied_edges = sorted(
        [
            {
                "edge_id": e["edge_id"],
                "source": e["source"],
                "target": e["target"],
                "weight": float(e["weight"]),
                "contribution": round(
                    activations.get(e["source"], 0.0) * float(e["weight"]), 15
                ),
            }
            for e in edges
            if e["source"] in activations and e["target"] in activations
        ],
        key=lambda e: (e["source"], e["target"], e["edge_id"]),
    )

    initial_out = {nid: activations[nid] for nid in all_node_ids}
    updated_out = {nid: updated[nid] for nid in all_node_ids}

    content_for_id = {
        "applied_edges": applied_edges,
        "initial_activations": initial_out,
        "source_graph_id": source_graph_id,
        "updated_activations": updated_out,
    }
    preview_id = "fcm_preview_" + _sha256(_canonical(content_for_id))[:24]

    return {
        "preview_id": preview_id,
        "source_graph_id": source_graph_id,
        "initial_activations": initial_out,
        "updated_activations": updated_out,
        "applied_edges": applied_edges,
        "status": "preview",
    }
