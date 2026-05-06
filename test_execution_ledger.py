from execution_ledger import build_run_record


def test_run_record_has_hashes():
    record = build_run_record(
        run_id="test_run",
        inputs={"a": 1},
        proposal={"b": 2},
        result={"c": 3},
    )

    assert record["run_id"] == "test_run"
    assert record["input_hash"]
    assert record["proposal_hash"]
    assert record["result_hash"]
    assert record["replay_hash"]


def test_replay_hash_is_deterministic_except_timestamp():
    a = build_run_record("r", {"x": 1}, {"y": 2}, {"z": 3})
    b = build_run_record("r", {"x": 1}, {"y": 2}, {"z": 3})

    a["timestamp"] = "fixed"
    b["timestamp"] = "fixed"

    from execution_ledger import sha256_obj
    assert sha256_obj(a) == sha256_obj(b)


if __name__ == "__main__":
    test_run_record_has_hashes()
    test_replay_hash_is_deterministic_except_timestamp()
    print("PASS: execution ledger tests")
