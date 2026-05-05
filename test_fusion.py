# BCLAW2 Phase 2 - Fusion Tests
from fusion import fuse
from worked_example import EXAMPLE_VALID

def test_fuse_passthrough():
    records = [EXAMPLE_VALID]
    result = fuse(records)
    assert result[0]["fused"] is True
    assert result[0]["id"] == EXAMPLE_VALID["id"]
    assert result[0]["value"] == EXAMPLE_VALID["value"]
    assert "conflict" not in result[0]

def test_fuse_two_records():
    r1 = {"id": "abc", "value": 42}
    r2 = {"id": "def", "value": 7}
    result = fuse([r1, r2])
    assert result[0] == {**r1, "fused": True}
    assert result[1] == {**r2, "fused": True}
    assert "conflict" not in result[0]
    assert "conflict" not in result[1]

def test_fuse_two_worked_examples():
    records = [EXAMPLE_VALID, EXAMPLE_VALID]
    result = fuse(records)
    assert len(result) == 1
    assert result[0]["fused"] is True
    assert result[0]["id"] == EXAMPLE_VALID["id"]
    assert result[0]["conflict"] is True

def test_fuse_preserves_id():
    r1 = {"id": "alpha", "value": 1}
    r2 = {"id": "beta", "value": 2}
    result = fuse([r1, r2])
    assert len(result) == 2
    assert result[0]["id"] == "alpha"
    assert result[1]["id"] == "beta"
    assert result[0]["fused"] is True
    assert result[1]["fused"] is True
    assert "conflict" not in result[0]
    assert "conflict" not in result[1]

def test_fuse_duplicate_id_keep_first():
    r1 = {"id": "same", "value": 1}
    r2 = {"id": "same", "value": 2}
    result = fuse([r1, r2])
    assert len(result) == 1
    assert result[0]["value"] == 1, f"expected first record (value=1), got value={result[0]['value']}"
    assert result[0]["fused"] is True
    assert not any(r["value"] == 2 for r in result), "second record must not be present"
    assert result[0]["conflict"] is True

def test_fuse_keep_last():
    r1 = {"id": "same", "value": 1}
    r2 = {"id": "same", "value": 2}
    result = fuse([r1, r2], strategy="keep_last")
    assert len(result) == 1
    assert result[0]["value"] == 2, f"expected last record (value=2), got value={result[0]['value']}"
    assert result[0]["fused"] is True
    assert not any(r["value"] == 1 for r in result), "first record must not be present"
    assert result[0]["conflict"] is True

if __name__ == "__main__":
    test_fuse_passthrough()
    print("PASS: fusion adds fused=True, no conflict on unique id")
    test_fuse_two_records()
    print("PASS: fusion two-record order and contents correct, no conflict")
    test_fuse_two_worked_examples()
    print("PASS: fusion duplicate worked examples — first kept, conflict=True")
    test_fuse_preserves_id()
    print("PASS: fusion preserves distinct ids in order, no conflict")
    test_fuse_duplicate_id_keep_first()
    print("PASS: fusion duplicate ids — first kept, conflict=True")
    test_fuse_keep_last()
    print("PASS: fusion keep_last — last kept, conflict=True")
