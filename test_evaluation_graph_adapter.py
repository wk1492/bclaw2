from evaluation_graph_adapter import snapshot_to_graph


def test_same_snapshot_same_graph_hash_despite_result_order():
    snapshot_a = {
        "results": [
            {"id": "candidate-b", "valid": True, "score": 0.8},
            {"id": "candidate-a", "valid": False, "score": 0.2},
        ]
    }

    snapshot_b = {
        "results": [
            {"score": 0.2, "valid": False, "id": "candidate-a"},
            {"score": 0.8, "id": "candidate-b", "valid": True},
        ]
    }

    g1 = snapshot_to_graph(snapshot_a)
    g2 = snapshot_to_graph(snapshot_b)

    assert g1.serialize() == g2.serialize()
    assert g1.graph_hash() == g2.graph_hash()


def test_graph_hash_changes_when_validation_changes():
    valid_snapshot = {"results": [{"id": "candidate-a", "valid": True, "score": 1.0}]}
    invalid_snapshot = {"results": [{"id": "candidate-a", "valid": False, "score": 0.0}]}

    assert snapshot_to_graph(valid_snapshot).graph_hash() != snapshot_to_graph(invalid_snapshot).graph_hash()


if __name__ == "__main__":
    test_same_snapshot_same_graph_hash_despite_result_order()
    test_graph_hash_changes_when_validation_changes()
    print("PASS: evaluation snapshot graph adapter")
