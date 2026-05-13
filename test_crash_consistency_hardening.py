"""
Crash consistency and append-boundary hardening.
Proves ledger verify/replay is fail-closed under interrupted writes.
"""
import json
import os
import tempfile

import pytest

from ledger_writer import LedgerWriter, verify_ledger
from transcript_ledger import verify_mixed_ledger

RUN_ID = "crash_consist_001"


def _fresh():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.unlink(path)
    return path


def _build_exec_ledger(path, n=3):
    writer = LedgerWriter(path)
    events = []
    for i in range(n):
        e = writer.append({"type": "execution.event", "payload": {"seq": i}})
        events.append(e)
    return events


# 1. torn final append: incomplete JSON line after valid complete lines
def test_torn_final_append_rejected():
    path = _fresh()
    _build_exec_ledger(path, 2)
    raw = open(path, "rb").read()
    assert raw.endswith(b"\n")
    # Append a new torn line (process died mid-write, no closing })
    with open(path, "ab") as f:
        f.write(b'{"type":"execution.event","payload":{"seq":99}')
    result = verify_ledger(path)
    assert result["ok"] is False
    assert len(result["failures"]) > 0
    assert any(
        kw in result["failures"][0]
        for kw in ("invalid JSON", "truncat", "newline", "terminator")
    )


# 2. missing final newline: complete JSON at EOF without \n terminator
def test_missing_final_newline_rejected():
    path = _fresh()
    _build_exec_ledger(path, 2)
    raw = open(path, "rb").read()
    assert raw.endswith(b"\n")
    # Strip the final newline — JSON is complete but unterminated
    with open(path, "wb") as f:
        f.write(raw[:-1])
    result = verify_ledger(path)
    assert result["ok"] is False
    assert len(result["failures"]) > 0
    assert any(
        kw in result["failures"][0]
        for kw in ("newline", "terminator", "trailing")
    )


# 3. verify_ledger and verify_mixed_ledger do not mutate the ledger file
def test_no_mutation_during_verification():
    path = _fresh()
    _build_exec_ledger(path, 3)
    before = open(path, "rb").read()

    r1 = verify_ledger(path)
    r2 = verify_ledger(path)
    r3 = verify_mixed_ledger(path)

    assert open(path, "rb").read() == before
    assert r1["ok"] is True
    assert r2["ok"] is True
    assert r3["ok"] is True


# 4. verify_mixed_ledger returns deterministic failure messages across repeated calls
def test_verify_mixed_ledger_deterministic_failures():
    path = _fresh()
    _build_exec_ledger(path, 2)
    lines = open(path).readlines()
    # Truncate second line mid-JSON
    with open(path, "w") as f:
        f.write(lines[0])
        f.write(lines[1][:25])

    results = [verify_mixed_ledger(path) for _ in range(5)]
    assert all(r["ok"] is False for r in results)
    msgs = [r["failures"] for r in results]
    assert all(m == msgs[0] for m in msgs[1:])


# 5. verification reports the first corrupt event index deterministically
def test_first_corrupt_event_index_deterministic():
    path = _fresh()
    _build_exec_ledger(path, 3)
    lines = open(path).readlines()
    # Remove middle event (index 1) — hash chain breaks at what is now line 2
    with open(path, "w") as f:
        f.write(lines[0])
        f.write(lines[2])

    results = [verify_ledger(path) for _ in range(5)]
    assert all(r["ok"] is False for r in results)
    first_msgs = [r["failures"][0] for r in results]
    assert len(set(first_msgs)) == 1, f"non-deterministic failure messages: {first_msgs}"
    assert "event 2" in first_msgs[0]


# 6. previous_hash continuity after clean truncation to N complete lines
def test_previous_hash_continuity_after_clean_truncation():
    path = _fresh()
    events = _build_exec_ledger(path, 3)

    # Truncate to first 2 complete lines (file still ends with \n)
    lines = open(path).readlines()
    with open(path, "w") as f:
        f.write(lines[0])
        f.write(lines[1])

    raw = open(path, "rb").read()
    assert raw.endswith(b"\n"), "truncated ledger must still end with newline"

    writer2 = LedgerWriter(path)
    assert writer2.current_rolling_hash == events[1]["rolling_hash"]

    new_event = writer2.append({"type": "after_truncation", "payload": {"x": 99}})
    assert new_event["previous_hash"] == events[1]["rolling_hash"]

    result = verify_ledger(path)
    assert result["ok"] is True
    assert result["count"] == 3


# 7. LedgerWriter refuses to initialize when the last line is corrupt
def test_ledger_writer_refuses_init_on_corrupt_tail():
    path = _fresh()
    _build_exec_ledger(path, 2)
    raw = open(path, "rb").read()
    # Append a torn line — last line will fail json.loads
    with open(path, "ab") as f:
        f.write(b'{"type":"torn","x":1')

    with pytest.raises((json.JSONDecodeError, ValueError)):
        LedgerWriter(path)
