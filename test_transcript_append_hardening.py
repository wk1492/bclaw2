"""
Append-only truncation hardening:
truncated final line, partial append, missing middle event,
append-only replay safety, deterministic failure messages,
canonical newline discipline.
"""
import json
import os
import tempfile

import pytest

from ledger_writer import LedgerWriter, verify_ledger
from transcript_event import make_transcript_event
from transcript_ledger import append_transcript_event, replay_transcript_events, verify_mixed_ledger

RUN_ID = "trunc_hardening_001"
TS_A = "2026-05-12T11:00:00+00:00"
TS_B = "2026-05-12T11:00:01+00:00"
TS_C = "2026-05-12T11:00:02+00:00"


def _fresh():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.unlink(path)
    return path


def _build_ledger(path, n=3):
    ts = [TS_A, TS_B, TS_C]
    events = []
    prev_id = None
    for i in range(n):
        event = make_transcript_event(
            run_id=RUN_ID, sender=f"agent_{i}", recipient="broadcast",
            role="proposal" if i == 0 else "critique",
            content=f"content {i}",
            created_at=ts[i],
            parent_message_id=prev_id,
            references=[prev_id] if prev_id else [],
        )
        append_transcript_event(event, path)
        events.append(event)
        prev_id = event["message_id"]
    return events


# 1. truncated final line detection
def test_truncated_final_line_detected():
    path = _fresh()
    _build_ledger(path, 2)

    raw = open(path, "rb").read()
    # Cut 20 bytes off the end — guaranteed to land inside the last JSON line
    with open(path, "wb") as f:
        f.write(raw[:-20])

    result = verify_ledger(path)
    assert result["ok"] is False
    assert len(result["failures"]) > 0
    msg = result["failures"][0]
    assert "invalid JSON" in msg or "truncat" in msg


# 2. partial append interruption detection
def test_partial_append_interruption_detected():
    path = _fresh()
    _build_ledger(path, 1)

    # Simulate interrupted write: a new line that is never closed
    with open(path, "a") as f:
        f.write('{"event_type":"transcript.message","content":"partial')

    result = verify_ledger(path)
    assert result["ok"] is False
    assert len(result["failures"]) > 0
    msg = result["failures"][0]
    # Message must not contain dynamic content
    assert "2026" not in msg
    assert "tmsg_" not in msg


# 3. missing middle event detection
def test_missing_middle_event_detected():
    path = _fresh()
    _build_ledger(path, 3)

    lines = open(path).readlines()
    assert len(lines) == 3
    # Remove the middle line — hash chain must catch it
    with open(path, "w") as f:
        f.write(lines[0])
        f.write(lines[2])

    result = verify_ledger(path)
    assert result["ok"] is False
    assert any("hash" in m for m in result["failures"])


# 4. append-only replay safety (idempotent, non-mutating)
def test_append_only_replay_safety():
    path = _fresh()
    _build_ledger(path, 3)

    before = open(path, "rb").read()

    r1 = json.dumps(replay_transcript_events(path), sort_keys=True, separators=(",", ":"))
    r2 = json.dumps(replay_transcript_events(path), sort_keys=True, separators=(",", ":"))
    r3 = json.dumps(replay_transcript_events(path), sort_keys=True, separators=(",", ":"))

    assert r1 == r2 == r3
    assert open(path, "rb").read() == before


# 5. deterministic failure messages
def test_failure_messages_are_deterministic():
    path = _fresh()
    _build_ledger(path, 2)

    lines = open(path).readlines()
    # Write first line complete, second line truncated to 20 chars
    with open(path, "w") as f:
        f.write(lines[0])
        f.write(lines[1][:20])

    r1 = verify_ledger(path)
    r2 = verify_ledger(path)
    r3 = verify_ledger(path)

    assert r1["ok"] is False
    assert r1["failures"] == r2["failures"] == r3["failures"]


# 6. canonical newline discipline
def test_canonical_newline_discipline():
    path = _fresh()
    _build_ledger(path, 3)

    raw = open(path, "rb").read()
    assert b"\r" not in raw
    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\n\n")

    lines = raw.decode("utf-8").splitlines()
    assert len(lines) == 3
    for line in lines:
        assert line.strip() != ""
        obj = json.loads(line)
        assert isinstance(obj, dict)
