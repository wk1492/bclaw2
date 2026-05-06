from graph_state import Edge, Node, make_graph


def test_same_logical_graph_same_hash_despite_insertion_order():
    g1 = make_graph(
        "g",
        nodes=[
            Node("B", "late fatigue", 0.2),
            Node("A", "early pace", 0.7),
        ],
        edges=[
            Edge("E2", "B", "A", -0.1),
            Edge("E1", "A", "B", 0.8),
        ],
    )

    g2 = make_graph(
        "g",
        nodes=[
            Node("A", "early pace", 0.7),
            Node("B", "late fatigue", 0.2),
        ],
        edges=[
            Edge("E1", "A", "B", 0.8),
            Edge("E2", "B", "A", -0.1),
        ],
    )

    assert g1.serialize() == g2.serialize()
    assert g1.graph_hash() == g2.graph_hash()


def test_metadata_order_does_not_change_hash():
    g1 = make_graph(
        "g",
        nodes=[Node("A", "pace", metadata={"z": 2, "a": 1})],
        edges=[],
        metadata={"b": 2, "a": 1},
    )

    g2 = make_graph(
        "g",
        nodes=[Node("A", "pace", metadata={"a": 1, "z": 2})],
        edges=[],
        metadata={"a": 1, "b": 2},
    )

    assert g1.serialize() == g2.serialize()
    assert g1.graph_hash() == g2.graph_hash()


def test_float_rounding_through_serializer_keeps_hash_stable():
    g1 = make_graph("g", nodes=[Node("A", "pace", 0.123456789123456)])
    g2 = make_graph("g", nodes=[Node("A", "pace", 0.123456789123499)])

    assert g1.serialize() == g2.serialize()
    assert g1.graph_hash() == g2.graph_hash()


if __name__ == "__main__":
    test_same_logical_graph_same_hash_despite_insertion_order()
    test_metadata_order_does_not_change_hash()
    test_float_rounding_through_serializer_keeps_hash_stable()
    print("PASS: deterministic graph state")
