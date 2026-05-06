from graph_state import Edge, GraphState, Node, make_graph
from evaluation_graph_adapter import snapshot_to_graph


def clamp(value, lo=-1.0, hi=1.0):
    return max(lo, min(hi, round(float(value), 12)))


def merge_evaluation_snapshot(current: GraphState, snapshot: dict) -> GraphState:
    incoming = snapshot_to_graph(snapshot, graph_id=current.graph_id)

    nodes = {n.node_id: n for n in current.nodes}
    edges = {e.edge_id: e for e in current.edges}

    for n in incoming.nodes:
        old = nodes.get(n.node_id)
        if old is None:
            nodes[n.node_id] = n
        else:
            nodes[n.node_id] = Node(
                node_id=old.node_id,
                label=old.label,
                activation=clamp((old.activation + n.activation) / 2.0),
                metadata={**old.metadata, **n.metadata},
            )

    for e in incoming.edges:
        old = edges.get(e.edge_id)
        if old is None:
            edges[e.edge_id] = e
        else:
            edges[e.edge_id] = Edge(
                edge_id=old.edge_id,
                source=old.source,
                target=old.target,
                weight=clamp((old.weight + e.weight) / 2.0),
                confidence=clamp((old.confidence + e.confidence) / 2.0, 0.0, 1.0),
                edge_type=old.edge_type,
                metadata={**old.metadata, **e.metadata},
            )

    return make_graph(
        graph_id=current.graph_id,
        nodes=tuple(nodes.values()),
        edges=tuple(edges.values()),
        metadata={**current.metadata, "last_update": "evaluation_snapshot"},
    )


def graph_update_event(before: GraphState, after: GraphState, update_type="evaluation_snapshot_merge"):
    return {
        "type": "graph_update",
        "update_type": update_type,
        "before_graph_hash": before.graph_hash(),
        "after_graph_hash": after.graph_hash(),
        "graph_id": after.graph_id,
    }
