"""
tests/unit/test_retention_policy.py

Unit tests for retention_policy module.

Invariants:
  1. All policies are pure: no I/O, no randomness, no wall-clock time
  2. All policies are deterministic: identical input → identical output
  3. All policies preserve relative order of surviving events
  4. All policies return subsets of the input (no new events synthesized)
  5. TailRetention backward-compatible with prior build_history_summary behavior
  6. ScoredRetention: top-N by score, order preserved
  7. EntropyRetention: top-N by content length, order preserved
  8. CompositeRetention: pipelines chain correctly
  9. build_history_summary delegates to supplied policy
  10. max_events=0 raises on all concrete policies
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from conversation_runner import DEFAULT_MAX_HISTORY_EVENTS, build_history_summary
from retention_policy import (
    CompositeRetention,
    EntropyRetention,
    RetentionPolicy,
    ScoredRetention,
    TailRetention,
)


# ── fixtures ───────────────────────────────────────────────────────────────────

def _events(n: int) -> list[dict]:
    return [
        {
            "message_id": f"tmsg_{i:024d}",
            "role": "proposal",
            "sender": f"agent_{i}",
            "content": "x" * (i + 1),      # length = i+1, strictly increasing
            "created_at": f"2026-05-20T10:{i:02d}:00+00:00",
            "event_type": "transcript.message",
            "timestamp": "2026-05-20T23:00:00+00:00",
            "event_hash": "a" * 64,
            "event_id": f"e{i}",
            "previous_hash": "0" * 64,
            "rolling_hash": "b" * 64,
        }
        for i in range(n)
    ]


# ── Protocol conformance ───────────────────────────────────────────────────────

def test_tail_retention_is_retention_policy():
    assert isinstance(TailRetention(5), RetentionPolicy)


def test_scored_retention_is_retention_policy():
    assert isinstance(ScoredRetention(lambda e: 1.0, 5), RetentionPolicy)


def test_entropy_retention_is_retention_policy():
    assert isinstance(EntropyRetention(5), RetentionPolicy)


def test_composite_retention_is_retention_policy():
    assert isinstance(CompositeRetention(TailRetention(5)), RetentionPolicy)


# ── TailRetention ──────────────────────────────────────────────────────────────

def test_tail_retention_keeps_last_n():
    events = _events(10)
    result = TailRetention(4).select(events)
    assert len(result) == 4
    assert result[0]["sender"] == "agent_6"
    assert result[-1]["sender"] == "agent_9"


def test_tail_retention_fewer_than_max_returns_all():
    events = _events(3)
    result = TailRetention(10).select(events)
    assert len(result) == 3


def test_tail_retention_exactly_max_returns_all():
    events = _events(5)
    assert len(TailRetention(5).select(events)) == 5


def test_tail_retention_empty_input():
    assert TailRetention(5).select([]) == []


def test_tail_retention_max_events_zero_raises():
    with pytest.raises(ValueError):
        TailRetention(0)


def test_tail_retention_deterministic():
    events = _events(10)
    assert TailRetention(4).select(events) == TailRetention(4).select(events)


def test_tail_retention_preserves_order():
    events = _events(8)
    result = TailRetention(5).select(events)
    senders = [r["sender"] for r in result]
    assert senders == sorted(senders, key=lambda s: int(s.split("_")[1]))


# ── ScoredRetention ────────────────────────────────────────────────────────────

def test_scored_retention_keeps_top_n_by_score():
    events = _events(10)
    # Score by sender index — keep top 3 (highest indices)
    scorer = lambda e: int(e["sender"].split("_")[1])
    result = ScoredRetention(scorer, 3).select(events)
    assert len(result) == 3
    senders = [r["sender"] for r in result]
    assert "agent_9" in senders
    assert "agent_8" in senders
    assert "agent_7" in senders


def test_scored_retention_preserves_relative_order():
    events = _events(10)
    scorer = lambda e: int(e["sender"].split("_")[1])
    result = ScoredRetention(scorer, 5).select(events)
    indices = [int(r["sender"].split("_")[1]) for r in result]
    assert indices == sorted(indices)


def test_scored_retention_fewer_than_max_returns_all():
    events = _events(3)
    result = ScoredRetention(lambda e: 1.0, 10).select(events)
    assert len(result) == 3


def test_scored_retention_empty_input():
    assert ScoredRetention(lambda e: 0.0, 5).select([]) == []


def test_scored_retention_max_events_zero_raises():
    with pytest.raises(ValueError):
        ScoredRetention(lambda e: 0.0, 0)


def test_scored_retention_deterministic():
    events = _events(10)
    scorer = lambda e: len(e["content"])
    r1 = ScoredRetention(scorer, 4).select(events)
    r2 = ScoredRetention(scorer, 4).select(events)
    assert r1 == r2


def test_scored_retention_tie_broken_by_position():
    # All events same score — tie should keep first N in original order
    events = _events(6)
    result = ScoredRetention(lambda e: 0.0, 3).select(events)
    senders = [r["sender"] for r in result]
    assert senders == ["agent_0", "agent_1", "agent_2"]


# ── EntropyRetention ──────────────────────────────────────────────────────────

def test_entropy_retention_keeps_longest_content():
    events = _events(10)
    # Content lengths: 1, 2, 3, ..., 10 — agent_9 has longest
    result = EntropyRetention(3).select(events)
    assert len(result) == 3
    senders = {r["sender"] for r in result}
    assert "agent_9" in senders
    assert "agent_8" in senders
    assert "agent_7" in senders


def test_entropy_retention_preserves_order():
    events = _events(8)
    result = EntropyRetention(4).select(events)
    indices = [int(r["sender"].split("_")[1]) for r in result]
    assert indices == sorted(indices)


def test_entropy_retention_deterministic():
    events = _events(10)
    assert EntropyRetention(4).select(events) == EntropyRetention(4).select(events)


def test_entropy_retention_max_events_zero_raises():
    with pytest.raises(ValueError):
        EntropyRetention(0)


# ── CompositeRetention ────────────────────────────────────────────────────────

def test_composite_single_policy_identical_to_direct():
    events = _events(10)
    policy = TailRetention(4)
    composite = CompositeRetention(TailRetention(4))
    assert policy.select(events) == composite.select(events)


def test_composite_chains_two_policies():
    # First: keep top-6 by content length (agent_4..9)
    # Then: tail-3 of those (agent_7, agent_8, agent_9)
    events = _events(10)
    scorer = lambda e: len(e["content"])
    result = CompositeRetention(
        ScoredRetention(scorer, 6),
        TailRetention(3),
    ).select(events)
    assert len(result) == 3
    senders = [r["sender"] for r in result]
    assert senders == ["agent_7", "agent_8", "agent_9"]


def test_composite_empty_policies_raises():
    with pytest.raises(ValueError):
        CompositeRetention()


def test_composite_deterministic():
    events = _events(10)
    scorer = lambda e: len(e["content"])
    p = CompositeRetention(ScoredRetention(scorer, 6), TailRetention(3))
    assert p.select(events) == p.select(events)


# ── build_history_summary integration ─────────────────────────────────────────

def test_build_history_summary_default_uses_tail():
    events = _events(15)
    summary = build_history_summary(events)
    assert len(summary) == DEFAULT_MAX_HISTORY_EVENTS
    # Last DEFAULT_MAX_HISTORY_EVENTS senders
    expected_last_sender = f"agent_{14}"
    assert summary[-1]["sender"] == expected_last_sender


def test_build_history_summary_custom_policy_used():
    events = _events(10)
    # Use entropy policy — should keep longest content (agents 7,8,9)
    summary = build_history_summary(events, retention_policy=EntropyRetention(3))
    assert len(summary) == 3
    senders = {e["sender"] for e in summary}
    assert "agent_9" in senders


def test_build_history_summary_custom_policy_ignores_max_events():
    events = _events(10)
    # Policy overrides max_events param
    summary = build_history_summary(
        events,
        max_events=2,
        retention_policy=TailRetention(5),
    )
    assert len(summary) == 5


def test_build_history_summary_policy_no_io():
    events = _events(5)
    with patch("builtins.open", side_effect=AssertionError("I/O forbidden")):
        result = build_history_summary(events, retention_policy=EntropyRetention(3))
    assert len(result) == 3


def test_build_history_summary_policy_deterministic():
    events = _events(10)
    policy = ScoredRetention(lambda e: len(e["content"]), 4)
    s1 = build_history_summary(events, retention_policy=policy)
    s2 = build_history_summary(events, retention_policy=policy)
    assert s1 == s2


# ── Purity: no datetime.now, no uuid ─────────────────────────────────────────

def test_tail_retention_no_datetime_now():
    events = _events(5)
    with patch("datetime.datetime") as mock_dt:
        mock_dt.now.side_effect = AssertionError("must not call datetime.now")
        TailRetention(3).select(events)


def test_scored_retention_no_uuid():
    import uuid as _uuid
    calls = []
    original = _uuid.uuid4
    _uuid.uuid4 = lambda: calls.append(1) or original()
    try:
        ScoredRetention(lambda e: 1.0, 3).select(_events(5))
    finally:
        _uuid.uuid4 = original
    assert calls == []
