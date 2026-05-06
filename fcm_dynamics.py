from graph_state import Edge, GraphState, Node, make_graph


def clamp(value, lo=-1.0, hi=1.0):
    return max(lo, min(hi, round(float(value), 12)))


def apply_fcm_step(graph: GraphState, damping=1.0) -> GraphState:
    node_map = {n.node_id: n for n in graph.nodes}
    incoming = {node_id: 0.0 for node_id in node_map}

    for edge in sorted(graph.edges, key=lambda e: (e.source, e.target, e.edge_type, e.edge_id)):
        source = node_map.get(edge.source)
        if source is None or edge.target not in incoming:
            continue
        incoming[edge.target] += source.activation * edge.weight * edge.confidence * damping

    new_nodes = []
    for node_id in sorted(node_map):
        old = node_map[node_id]
        new_nodes.append(
            Node(
                node_id=old.node_id,
                label=old.label,
                activation=clamp(old.activation + incoming[node_id]),
                metadata=old.metadata,
            )
        )

    return make_graph(
        graph_id=graph.graph_id,
        nodes=tuple(new_nodes),
        edges=tuple(graph.edges),
        metadata={**graph.metadata, "last_dynamics": "fcm_step"},
    )


def apply_fcm_steps(graph: GraphState, steps=1, damping=1.0):
    trajectory = [graph.graph_hash()]
    current = graph

    for _ in range(steps):
        current = apply_fcm_step(current, damping=damping)
        trajectory.append(current.graph_hash())

    return {
        "final_graph": current,
        "trajectory": trajectory,
    }
