from execution_ledger import build_run_record, hash_record_payload


def test_run_record_has_hash():
    r = build_run_record("test", {"a": 1}, {"b": 2}, timestamp="fixed")
    assert "hash" in r
    assert len(r["hash"]) == 64
    assert r["hash"] == hash_record_payload(r)


def test_replay_hash_is_deterministic():
    a = build_run_record("r", {"x": 1}, {"y": 2}, {"z": 3}, timestamp="fixed")
    b = build_run_record("r", {"x": 1}, {"y": 2}, {"z": 3}, timestamp="fixed")
    assert a["hash"] == b["hash"]


if __name__ == "__main__":
    test_run_record_has_hash()
    test_replay_hash_is_deterministic()
    print("PASS: execution ledger tests")
