from edge_arbitration import arbitrate_edge


def test_confidence_weighted_average():
    result = arbitrate_edge(
        "E1",
        "A",
        "B",
        [
            {"agent": "one", "weight": 0.8, "confidence": 0.9},
            {"agent": "two", "weight": 0.6, "confidence": 0.7},
        ],
    )

    assert result["final_weight"] == 0.7125
    assert result["final_confidence"] == 0.8
    assert result["disagreement"] == 0.2


def test_rejects_empty():
    try:
        arbitrate_edge("E1", "A", "B", [])
        raise AssertionError("empty proposals should fail")
    except ValueError:
        pass


if __name__ == "__main__":
    test_confidence_weighted_average()
    test_rejects_empty()
    print("PASS: edge arbitration tests")
