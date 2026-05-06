from replay_runner import count_types, replay_summary


def test_count_types():
    records = [
        {"type": "a", "event_hash": "h1"},
        {"type": "a", "event_hash": "h2"},
        {"type": "b", "event_hash": "h3"},
    ]

    assert count_types(records) == {"a": 2, "b": 1}


def test_replay_summary():
    records = [{"type": "run", "event_hash": "abc"}]

    summary = replay_summary(records)

    assert summary["record_count"] == 1
    assert summary["types"] == {"run": 1}
    assert summary["hashes"] == ["abc"]


if __name__ == "__main__":
    test_count_types()
    test_replay_summary()
    print("PASS: replay runner tests")
