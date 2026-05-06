from graph_state import GraphState


def test_add_node_and_edge():
    g = GraphState()
    g.add_node("A", "cause", 0.5)
    g.add_node("B", "effect", 0.0)
    g.add_edge("E1", "A", "B", 0.75, confidence=0.8)

    assert g.nodes["A"].activation == 0.5
    assert g.edges["E1"].weight == 0.75
    assert len(g.incoming_edges("B")) == 1
    assert g.version == 3


def test_clamps_values():
    g = GraphState()
    g.add_node("A", "too high", 9.0)
    assert g.nodes["A"].activation == 1.0

    g.set_activation("A", -9.0)
    assert g.nodes["A"].activation == -1.0


if __name__ == "__main__":
    test_add_node_and_edge()
    test_clamps_values()
    print("PASS: graph_state tests")
