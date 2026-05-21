"""
retention_policy.py — SUBSTRATE_VERSION=1

Pluggable retention policies for history_summary construction.

AUTHORITY BOUNDARY
------------------
Retention policies operate on already-replayed transcript events.
They are pure functions of the event list: no I/O, no randomness, no
wall-clock time. Same input always produces same output.

The ledger is never pruned. Forgetting is a view-layer operation only.
This preserves the audit and replay invariants unconditionally.

SEPARATION
----------
  Ledger   — complete historical record, append-only, never pruned
  Summary  — bounded working view, controlled by retention policy

A system that forgets at the summary layer while preserving the ledger
can always reconstruct full history on demand. A system that forgets at
the ledger layer cannot. This distinction is the foundation of
replay-safe controlled forgetting.
"""
from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable


@runtime_checkable
class RetentionPolicy(Protocol):
    """
    Pure deterministic selector over a list of transcript events.

    select(events) receives the full replay-ordered event list and returns
    the subset to include in history_summary. The returned list must be:
      - a subset of the input events
      - in the same relative order as the input (no reordering)
      - deterministic: identical input → identical output
      - free of I/O, randomness, and wall-clock time
    """

    def select(self, events: list[dict]) -> list[dict]:
        ...


# ── TailRetention ─────────────────────────────────────────────────────────────

class TailRetention:
    """
    Keep the most recent N events (tail truncation).

    Default behavior. Equivalent to events[-max_events:].
    Deterministic and order-preserving.
    """

    def __init__(self, max_events: int) -> None:
        if max_events < 1:
            raise ValueError("max_events must be at least 1")
        self.max_events = max_events

    def select(self, events: list[dict]) -> list[dict]:
        return events[-self.max_events:] if len(events) > self.max_events else list(events)


# ── ScoredRetention ───────────────────────────────────────────────────────────

class ScoredRetention:
    """
    Keep the top N events by caller-supplied score, in original order.

    scorer_fn receives one event dict and returns a float. Higher scores
    survive. Ties are broken by original position (earlier position wins
    among equal-scored events, preserving temporal coherence).

    The scoring function must be deterministic and pure.
    """

    def __init__(
        self,
        scorer_fn: Callable[[dict], float],
        max_events: int,
    ) -> None:
        if max_events < 1:
            raise ValueError("max_events must be at least 1")
        self.scorer_fn = scorer_fn
        self.max_events = max_events

    def select(self, events: list[dict]) -> list[dict]:
        if len(events) <= self.max_events:
            return list(events)
        scored = sorted(
            enumerate(events),
            key=lambda pair: (-self.scorer_fn(pair[1]), pair[0]),
        )
        kept_indices = sorted(idx for idx, _ in scored[: self.max_events])
        return [events[i] for i in kept_indices]


# ── EntropyRetention ──────────────────────────────────────────────────────────

class EntropyRetention:
    """
    Keep the N events with highest content length (proxy for information density).

    Longer content is treated as higher information density. Events are
    selected by descending content length; ties broken by original position.
    Relative order of surviving events is preserved.

    This is a structural proxy only. For domain-specific entropy scoring,
    use ScoredRetention with a custom scorer_fn.
    """

    def __init__(self, max_events: int) -> None:
        if max_events < 1:
            raise ValueError("max_events must be at least 1")
        self.max_events = max_events

    def select(self, events: list[dict]) -> list[dict]:
        return ScoredRetention(
            scorer_fn=lambda e: len(e.get("content", "")),
            max_events=self.max_events,
        ).select(events)


# ── CompositeRetention ────────────────────────────────────────────────────────

class CompositeRetention:
    """
    Apply policies sequentially: output of each policy feeds the next.

    Useful for pipelines like: first score-select, then tail-truncate.
    Each policy in the chain sees only the survivors from the previous stage.
    """

    def __init__(self, *policies: RetentionPolicy) -> None:
        if not policies:
            raise ValueError("CompositeRetention requires at least one policy")
        self._policies = policies

    def select(self, events: list[dict]) -> list[dict]:
        result = list(events)
        for policy in self._policies:
            result = policy.select(result)
        return result
