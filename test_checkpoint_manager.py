import json

from checkpoint_manager import CheckpointManager
from state_serializer import state_hash


def test_checkpoint_envelope_roundtrip():
    mgr = CheckpointManager()

    state = {
        "b": 2,
        "a": {"value": 0.30000000000000004},
    }

    path = mgr.create_checkpoint(
        "test_state",
        state,
        checkpoint_id="cp_test_envelope",
        parent_hash="0" * 64,
        ledger_offset=12,
    )

    restored = mgr.load_checkpoint(path)

    assert restored["checkpoint_id"] == "cp_test_envelope"
    assert restored["schema_version"] == "1"
    assert restored["serializer_version"] == "1"
    assert restored["parent_hash"] == "0" * 64
    assert restored["ledger_offset"] == 12
    assert restored["state_hash"] == state_hash(state)


def test_checkpoint_detects_tampering():
    mgr = CheckpointManager()

    path = mgr.create_checkpoint(
        "tamper_test",
        {"x": 1},
        checkpoint_id="cp_tamper_test",
    )

    data = json.loads(path.read_text())
    data["state"]["x"] = 2
    path.write_text(json.dumps(data, indent=2, sort_keys=True))

    try:
        mgr.load_checkpoint(path)
        raise AssertionError("tampered checkpoint should fail")
    except ValueError:
        pass


if __name__ == "__main__":
    test_checkpoint_envelope_roundtrip()
    test_checkpoint_detects_tampering()
    print("PASS: checkpoint manager tests")
