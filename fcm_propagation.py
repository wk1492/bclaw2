from graph_state import clamp


def compute_next_activations(graph):
    current = {
        node_id: node.activation
        for node_id, node in graph.nodes.items()
    }

    next_values = dict(current)

    for node_id in graph.nodes:
        influence = 0.0
        for edge in graph.incoming_edges(node_id):
            influence += current[edge.source] * edge.weight
        next_values[node_id] = clamp(current[node_id] + influence)

    return next_values


def propagate_once(graph, source="fcm_propagation"):
    next_values = compute_next_activations(graph)

    updates = []
    for node_id, value in next_values.items():
        old = graph.nodes[node_id].activation
        if value != old:
            graph.set_activation(node_id, value, source=source)
            updates.append({
                "node_id": node_id,
                "old": old,
                "new": value,
            })

    return updates


if __name__ == "__main__":
    from graph_state import GraphState

    g = GraphState()
    g.add_node("A", "early pace pressure", 0.7)
    g.add_node("B", "late fatigue", 0.0)
    g.add_edge("E1", "A", "B", 0.8)

    updates = propagate_once(g)
    print(updates)
