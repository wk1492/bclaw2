import json

from ledger_writer import LedgerWriter, verify_ledger


def _write_two_events(path):
    writer = LedgerWriter(path)
    writer.append({"event_type": "test_event", "payload": {"x": 1}})
    writer.append({"event_type": "test_event", "payload": {"x": 2}})


# 1. Truncated partial JSON line is detected as invalid
def test_truncated_line_detected(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _write_two_events(path)

    with path.open("a", encoding="utf-8") as f:
        f.write('{"event_type": "test", "incom\n')

    result = verify_ledger(path)
    assert result["ok"] is False
    assert any(
        "invalid json" in f.lower() or "json" in f.lower()
        for f in result["failures"]
    )


# 2. Whitespace-only partial line (no terminating newline) is detected
def test_empty_partial_line_detected(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _write_two_events(path)

    # Append whitespace without a trailing newline — file no longer ends with LF,
    # which verify_ledger detects as a missing final newline terminator.
    path.write_bytes(path.read_bytes() + b"   ")

    result = verify_ledger(path)
    assert result["ok"] is False


# 3. Valid events are counted before the failure point
def test_valid_events_counted_before_failure(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _write_two_events(path)

    with path.open("a", encoding="utf-8") as f:
        f.write('{"event_type": "test", "incom\n')

    result = verify_ledger(path)
    # verify_ledger sets count to the line number of the failing event (3 here),
    # so at least both valid events were seen before the failure.
    assert result["count"] >= 2


# 4. verify_ledger does not modify the file (read-only)
def test_no_repair_or_mutation(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _write_two_events(path)

    with path.open("a", encoding="utf-8") as f:
        f.write('{"event_type": "test", "incom\n')

    before_bytes = path.read_bytes()
    verify_ledger(path)
    after_bytes = path.read_bytes()

    assert before_bytes == after_bytes


# 5. The two valid events remain parseable after corruption
def test_original_valid_events_still_parseable(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _write_two_events(path)

    with path.open("a", encoding="utf-8") as f:
        f.write('{"event_type": "test", "incom\n')

    lines = path.read_text().splitlines()[:2]
    assert len(lines) == 2
    for line in lines:
        event = json.loads(line)
        assert "event_type" in event


# 6. A clean ledger passes verification with correct count and empty failures
def test_clean_ledger_passes_verification(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _write_two_events(path)

    result = verify_ledger(path)
    assert result["ok"] is True
    assert result["count"] == 2
    assert result["failures"] == []
