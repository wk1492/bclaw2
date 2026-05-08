from deterministic_message_id import generate_message_id


def test_same_inputs_same_id():
    a = generate_message_id("cand-001", "loop", "worker_a", "user", 0)
    b = generate_message_id("cand-001", "loop", "worker_a", "user", 0)
    assert a == b, f"expected same id, got {a!r} vs {b!r}"


def test_different_turn_different_id():
    a = generate_message_id("cand-001", "loop", "worker_a", "user", 0)
    b = generate_message_id("cand-001", "loop", "worker_a", "user", 1)
    assert a != b


def test_different_sender_different_id():
    a = generate_message_id("cand-001", "loop", "worker_a", "user", 0)
    b = generate_message_id("cand-001", "worker_b", "worker_a", "user", 0)
    assert a != b


def test_format():
    mid = generate_message_id("cand-001", "s", "r", "user", 0)
    assert mid.startswith("msg_")
    assert len(mid) == 68  # "msg_" + 64 hex chars


def test_no_timestamp_in_id():
    import re
    mid = generate_message_id("cand-001", "s", "r", "user", 0)
    # ID must be exactly msg_ followed by 64 lowercase hex chars — no separators, colons, or hyphens
    assert re.fullmatch(r"msg_[0-9a-f]{64}", mid), f"ID format violation: {mid!r}"


if __name__ == "__main__":
    test_same_inputs_same_id()
    print("PASS: same inputs produce same ID")
    test_different_turn_different_id()
    print("PASS: different turn produces different ID")
    test_different_sender_different_id()
    print("PASS: different sender produces different ID")
    test_format()
    print("PASS: ID format is msg_<64hex>")
    test_no_timestamp_in_id()
    print("PASS: no timestamp digits in ID")
