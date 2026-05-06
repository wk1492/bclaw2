from graph_state import make_graph
from graph_update import graph_update_event, merge_evaluation_snapshot


def test_same_snapshot_sequence_same_hash_trajectory():
    base1 = make_graph("g")
    base2 = make_graph("g")

    snapshots = [
        {"results": [{"id": "candidate-a", "valid": True, "score": 0.8}]},
        {"results": [{"id": "candidate-b", "valid": False, "score": 0.2}]},
    ]

    trajectory1 = []
    trajectory2 = []

    g = base1
    for s in snapshots:
        nxt = merge_evaluation_snapshot(g, s)
        trajectory1.append((g.graph_hash(), nxt.graph_hash()))
        g = nxt

    g = base2
    for s in snapshots:
        nxt = merge_evaluation_snapshot(g, s)
        trajectory2.append((g.graph_hash(), nxt.graph_hash()))
        g = nxt

    assert trajectory1 == trajectory2


def test_graph_update_event_records_before_and_after_hashes():
    before = make_graph("g")
    after = merge_evaluation_snapshot(
        before,
        {"results": [{"id": "candidate-a", "valid": True, "score": 0.8}]},
    )

    event = graph_update_event(before, after)

    assert event["type"] == "graph_update"
    assert event["before_graph_hash"] == before.graph_hash()
    assert event["after_graph_hash"] == after.graph_hash()
    assert event["before_graph_hash"] != event["after_graph_hash"]


if __name__ == "__main__":
    test_same_snapshot_sequence_same_hash_trajectory()
    test_graph_update_event_records_before_and_after_hashes()
    print("PASS: deterministic graph update layer")
