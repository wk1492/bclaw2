from causal_tape import replay_from_empty


def test_same_snapshot_sequence_same_trajectory_and_events():
    snapshots = [
        {"results": [{"id": "candidate-a", "valid": True, "score": 0.8}]},
        {"results": [{"id": "candidate-b", "valid": False, "score": 0.2}]},
        {"results": [{"id": "candidate-a", "valid": True, "score": 1.0}]},
    ]

    a = replay_from_empty(snapshots)
    b = replay_from_empty(snapshots)

    assert a["trajectory"] == b["trajectory"]
    assert a["events"] == b["events"]
    assert a["final_graph"].graph_hash() == b["final_graph"].graph_hash()


def test_different_snapshot_sequence_changes_trajectory():
    snapshots_a = [
        {"results": [{"id": "candidate-a", "valid": True, "score": 0.8}]},
    ]

    snapshots_b = [
        {"results": [{"id": "candidate-a", "valid": False, "score": 0.2}]},
    ]

    a = replay_from_empty(snapshots_a)
    b = replay_from_empty(snapshots_b)

    assert a["trajectory"] != b["trajectory"]
    assert a["final_graph"].graph_hash() != b["final_graph"].graph_hash()


def test_event_chain_matches_trajectory():
    snapshots = [
        {"results": [{"id": "candidate-a", "valid": True, "score": 0.8}]},
        {"results": [{"id": "candidate-b", "valid": False, "score": 0.2}]},
    ]

    result = replay_from_empty(snapshots)

    for i, event in enumerate(result["events"]):
        assert event["before_graph_hash"] == result["trajectory"][i]
        assert event["after_graph_hash"] == result["trajectory"][i + 1]
        assert event["sequence_index"] == i


if __name__ == "__main__":
    test_same_snapshot_sequence_same_trajectory_and_events()
    test_different_snapshot_sequence_changes_trajectory()
    test_event_chain_matches_trajectory()
    print("PASS: deterministic causal tape replay")
