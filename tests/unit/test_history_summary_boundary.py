"""
TASK_34 — deterministic/non-authoritative history_summary boundary tests.

All tests operate on in-memory event lists or temp ledger files.
No model calls. No wall-clock timestamps introduced by test code.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from conversation_runner import (
    DEFAULT_MAX_HISTORY_EVENTS,
    _LEDGER_INTERNAL_FIELDS,
    _safe_result_view,
    build_history_summary,
    run_conversation,
)
from transcript_llm_agent import fake_model, run_agent_turn

_TS_BASE = "2026-05-20T10:{:02d}:00+00:00"


def _make_ledger(n_turns: int) -> Path:
    """Create a temp ledger with n_turns proposal events using fake_model."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    for i in range(n_turns):
        run_agent_turn(
            f"agent_{i}", "proposal", [], path,
            run_id="test_run", created_at=_TS_BASE.format(i),
            model_fn=fake_model,
        )
    return path


def _make_events(n: int) -> list[dict]:
    """Synthetic minimal event dicts (no ledger I/O)."""
    return [
        {
            "message_id": f"tmsg_{i:024d}",
            "role": "proposal",
            "sender": f"agent_{i}",
            "content": f"content {i}",
            "created_at": _TS_BASE.format(i),
            "event_type": "transcript.message",
            "timestamp": "2026-05-20T23:00:00+00:00",
            "event_hash": "a" * 64,
            "event_id": f"evt_{i}",
            "previous_hash": "0" * 64,
            "rolling_hash": "b" * 64,
        }
        for i in range(n)
    ]


# ── 1. identical event history → identical history_summary ─────────────────────

def test_identical_events_produce_identical_history_summary():
    events = _make_events(5)
    s1 = build_history_summary(events)
    s2 = build_history_summary(events)
    assert s1 == s2


def test_identical_ledger_produces_identical_run_conversation():
    path = _make_ledger(3)
    r1 = run_conversation(path)
    r2 = run_conversation(path)
    assert r1["history_summary"] == r2["history_summary"]


# ── 2. truncation is deterministic ────────────────────────────────────────────

def test_truncation_takes_tail():
    events = _make_events(15)
    summary = build_history_summary(events, max_events=5)
    assert len(summary) == 5
    expected_senders = [f"agent_{i}" for i in range(10, 15)]
    assert [e["sender"] for e in summary] == expected_senders


def test_truncation_identical_for_identical_input():
    events = _make_events(20)
    s1 = build_history_summary(events, max_events=7)
    s2 = build_history_summary(events, max_events=7)
    assert s1 == s2


def test_no_truncation_when_events_fewer_than_max():
    events = _make_events(3)
    summary = build_history_summary(events, max_events=10)
    assert len(summary) == 3


def test_max_events_zero_raises():
    with pytest.raises(ValueError):
        build_history_summary(_make_events(3), max_events=0)


# ── 3. include_history=False produces no history_summary ──────────────────────

def test_include_history_false_absent_from_result():
    path = _make_ledger(2)
    result = run_conversation(path, include_history=False)
    assert "history_summary" not in result


def test_include_history_true_present_in_result():
    path = _make_ledger(2)
    result = run_conversation(path, include_history=True)
    assert "history_summary" in result
    assert isinstance(result["history_summary"], list)


def test_include_history_echoed_in_result():
    path = _make_ledger(1)
    assert run_conversation(path, include_history=False)["include_history"] is False
    assert run_conversation(path, include_history=True)["include_history"] is True


# ── 4. replay never calls model during reconstruction ─────────────────────────

def test_run_conversation_never_calls_model():
    path = _make_ledger(3)
    with patch("conversation_runner.replay_transcript_events") as mock_replay:
        mock_replay.return_value = _make_events(3)
        run_conversation(path)
    # replay_transcript_events called once; no model import touched
    mock_replay.assert_called_once()


def test_build_history_summary_performs_no_io(tmp_path):
    events = _make_events(5)
    # If build_history_summary tried to open a file, this would raise
    with patch("builtins.open", side_effect=AssertionError("I/O forbidden")):
        result = build_history_summary(events)
    assert len(result) == 5


# ── 5. descriptive_timestamp marked non-authoritative ─────────────────────────

def test_safe_result_view_renames_timestamp():
    event = _make_events(1)[0]
    view = _safe_result_view(event)
    assert "timestamp" not in view
    assert "descriptive_timestamp" in view
    assert view["descriptive_timestamp"] == event["timestamp"]


def test_history_summary_has_descriptive_timestamp_not_timestamp():
    events = _make_events(3)
    summary = build_history_summary(events)
    for entry in summary:
        assert "timestamp" not in entry
        assert "descriptive_timestamp" in entry


# ── 6. no wall-clock time introduced ─────────────────────────────────────────

def test_no_datetime_now_in_build_history_summary():
    from unittest.mock import patch
    events = _make_events(5)
    with patch("datetime.datetime") as mock_dt:
        mock_dt.now.side_effect = AssertionError("datetime.now() must not be called")
        # Must not raise — build_history_summary must not call datetime.now
        result = build_history_summary(events)
    assert len(result) == 5


# ── 7. no random/uuid generation ─────────────────────────────────────────────

def test_no_uuid_in_history_summary():
    import uuid as _uuid
    events = _make_events(5)
    original_uuid4 = _uuid.uuid4
    calls = []
    _uuid.uuid4 = lambda: calls.append(1) or original_uuid4()
    try:
        build_history_summary(events)
    finally:
        _uuid.uuid4 = original_uuid4
    assert calls == [], "build_history_summary must not generate UUIDs"


# ── 8. history_summary derived from replay only ───────────────────────────────

def test_history_summary_content_matches_events():
    events = _make_events(4)
    summary = build_history_summary(events)
    for i, entry in enumerate(summary):
        assert entry["content"] == events[i]["content"]
        assert entry["sender"] == events[i]["sender"]
        assert entry["message_id"] == events[i]["message_id"]


def test_ledger_internal_fields_stripped():
    events = _make_events(2)
    summary = build_history_summary(events)
    for entry in summary:
        for field in _LEDGER_INTERNAL_FIELDS:
            assert field not in entry, f"ledger-internal field {field!r} must be stripped"


def test_run_conversation_empty_ledger():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    result = run_conversation(path)
    assert result["event_count"] == 0
    assert result["latest_event"] is None
    assert result["history_summary"] == []
