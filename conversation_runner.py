"""
conversation_runner.py — replay-derived conversation state for BCLAW2.

AUTHORITY BOUNDARY
------------------
This module derives convenience context from replayed transcript events.
It never calls models, never writes to the ledger, and never mutates
prior events. The canonical record of what happened is always the
transcript events in the ledger — not anything produced here.

Changing history_summary construction rules requires explicit version review
(see docs/design/history_summary_boundary.md).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from transcript_ledger import replay_transcript_events

# Fields written by the ledger layer that carry no semantic authority.
# Excluded from safe views so callers cannot accidentally treat them as
# canonical identity or causal ordering signals.
_LEDGER_INTERNAL_FIELDS = frozenset({
    "event_hash",
    "event_id",
    "previous_hash",
    "rolling_hash",
})

# How many events to include in a history_summary when the caller does
# not specify a limit. Bounded to prevent unbounded context growth.
DEFAULT_MAX_HISTORY_EVENTS = 10


def _safe_result_view(event: dict[str, Any]) -> dict[str, Any]:
    """
    Return a non-authoritative, read-only view of one transcript event.

    Strips ledger-internal hash-chain fields. Renames 'timestamp' to
    'descriptive_timestamp' to make explicit that this value is the
    wall-clock time the ledger writer appended the record — it is
    informational only and must never be used for causal ordering or
    replay reconstruction.
    """
    view: dict[str, Any] = {}
    for k, v in event.items():
        if k in _LEDGER_INTERNAL_FIELDS:
            continue
        if k == "timestamp":
            view["descriptive_timestamp"] = v
        else:
            view[k] = v
    return view


# NON-AUTHORITATIVE replay-derived convenience context.
# Deterministic and bounded only.
# Must never become canonical cognition state.
# Replay truth remains recorded transcript events.

def build_history_summary(
    events: list[dict[str, Any]],
    max_events: int = DEFAULT_MAX_HISTORY_EVENTS,
) -> list[dict[str, Any]]:
    """
    Produce a bounded, deterministic summary of recent transcript events.

    Rules (all mandatory):
    - Derived solely from already-replayed transcript events (no I/O here).
    - Ordered by topology linearization — the order replay_transcript_events
      returned them in. Never re-sorted or shuffled.
    - Bounded: at most max_events events included (tail truncation —
      most recent N events).
    - Deterministic truncation: identical input always produces identical
      output. No randomness, no wall-clock time, no UUIDs introduced.
    - Each event passed through _safe_result_view (strips internal fields,
      renames timestamp).
    - Prior events are never mutated.
    """
    if max_events < 1:
        raise ValueError("max_events must be at least 1")

    bounded = events[-max_events:] if len(events) > max_events else events
    return [_safe_result_view(e) for e in bounded]


def run_conversation(
    ledger_path: str | Path,
    *,
    include_history: bool = True,
    max_history_events: int = DEFAULT_MAX_HISTORY_EVENTS,
) -> dict[str, Any]:
    """
    Derive current conversation state entirely from the ledger.

    Does NOT call any model. Does NOT write to the ledger. Does NOT
    introduce wall-clock time or random values. Safe to call repeatedly
    on the same ledger — always produces the same result for the same
    ledger content.

    Returns:
        event_count       — total transcript events in ledger
        latest_event      — _safe_result_view of the most recent event, or None
        history_summary   — bounded safe views if include_history=True, else absent
        include_history   — echoed so callers can verify the flag they set
    """
    events = replay_transcript_events(Path(ledger_path))

    result: dict[str, Any] = {
        "event_count": len(events),
        "latest_event": _safe_result_view(events[-1]) if events else None,
        "include_history": include_history,
    }

    # NON-AUTHORITATIVE replay-derived convenience context.
    # Deterministic and bounded only.
    # Must never become canonical cognition state.
    # Replay truth remains recorded transcript events.
    if include_history:
        result["history_summary"] = build_history_summary(events, max_history_events)

    return result
