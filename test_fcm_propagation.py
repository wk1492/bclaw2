from graph_state import GraphState
from fcm_propagation import compute_next_activations, propagate_once


def test_single_edge_propagates_activation():
    g = GraphState()
    g.add_node("A", "cause", 0.7)
    g.add_node("B", "effect", 0.0)
    g.add_edge("E1", "A", "B", 0.8)

    next_values = compute_next_activations(g)
    assert next_values["A"] == 0.7
    assert round(next_values["B"], 6) == 0.56


def test_propagate_once_updates_graph():
    g = GraphState()
    g.add_node("A", "cause", 0.7)
    g.add_node("B", "effect", 0.0)
    g.add_edge("E1", "A", "B", 0.8)

    updates = propagate_once(g)
    assert updates == [{"node_id": "B", "old": 0.0, "new": 0.5599999999999999}]
    assert round(g.nodes["B"].activation, 6) == 0.56


def test_clamps_propagation():
    g = GraphState()
    g.add_node("A", "big cause", 1.0)
    g.add_node("B", "already high", 0.9)
    g.add_edge("E1", "A", "B", 0.8)

    propagate_once(g)
    assert g.nodes["B"].activation == 1.0


if __name__ == "__main__":
    test_single_edge_propagates_activation()
    test_propagate_once_updates_graph()
    test_clamps_propagation()
    print("PASS: fcm propagation tests")
