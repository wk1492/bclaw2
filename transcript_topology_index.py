"""
transcript_topology_index.py — SUBSTRATE_VERSION=1

Pure deterministic index over transcript event topology.

Accepts ordered transcript events; builds parent/child/depth/sibling
lookup structures. All ordering is by input insertion index — no
timestamps, no randomness. Input events are never mutated.

The ledger, replay engine, hash-chain, and canonical serialization are
not touched by this module.
"""
from __future__ import annotations

import json
from typing import Any

_TRANSCRIPT = "transcript.message"


class TranscriptTopologyIndex:
    """
    Deterministic read-only index over a transcript event list.

    Traversal order = canonical insertion order (position in input list).
    Children of the same parent are ordered by insertion index.
    Orphans = events whose parent_message_id is absent from this set.
    """

    def __init__(self, events: list[dict[str, Any]]) -> None:
        transcript = [e for e in events if e.get("event_type") == _TRANSCRIPT]

        self._events: list[dict] = transcript
        self._idx: dict[str, int] = {e["message_id"]: i for i, e in enumerate(transcript)}
        self._by_id: dict[str, dict] = {e["message_id"]: e for e in transcript}
        self._parent: dict[str, str | None] = {}
        self._children: dict[str, list[str]] = {e["message_id"]: [] for e in transcript}
        self._orphan_set: set[str] = set()

        for e in transcript:
            mid = e["message_id"]
            pid = e.get("parent_message_id")
            if pid is None:
                self._parent[mid] = None
            elif pid in self._by_id:
                self._parent[mid] = pid
                self._children[pid].append(mid)
            else:
                self._parent[mid] = None
                self._orphan_set.add(mid)

    # ── lookups ───────────────────────────────────────────────────────────────

    def parent(self, message_id: str) -> str | None:
        """Parent message_id, or None for roots and orphans."""
        return self._parent.get(message_id)

    def children(self, message_id: str) -> list[str]:
        """Children in insertion order."""
        return list(self._children.get(message_id, []))

    def roots(self) -> list[str]:
        """Events with no parent_message_id, in insertion order. Excludes orphans."""
        return [
            e["message_id"] for e in self._events
            if e.get("parent_message_id") is None
        ]

    def is_root(self, message_id: str) -> bool:
        return (
            message_id in self._by_id
            and self._by_id[message_id].get("parent_message_id") is None
            and message_id not in self._orphan_set
        )

    def siblings(self, message_id: str) -> list[str]:
        """All children of the same parent, in insertion order, excluding self."""
        pid = self._parent.get(message_id)
        if pid is None:
            siblings = self.roots()
        else:
            siblings = self._children.get(pid, [])
        return [mid for mid in siblings if mid != message_id]

    def depth(self, message_id: str) -> int:
        """Distance from root. Roots = 0. Cycle-safe."""
        d, current, seen = 0, message_id, set()
        while True:
            p = self._parent.get(current)
            if p is None:
                return d
            if p in seen:
                return d
            seen.add(p)
            d += 1
            current = p

    def ancestors(self, message_id: str) -> list[str]:
        """From immediate parent to root, in ascending order. Cycle-safe."""
        result, current, seen = [], message_id, set()
        while True:
            p = self._parent.get(current)
            if p is None or p in seen:
                return result
            seen.add(p)
            result.append(p)
            current = p

    def descendants(self, message_id: str) -> list[str]:
        """BFS descendants, children in insertion order. Cycle-safe."""
        result, queue, seen = [], list(self._children.get(message_id, [])), set()
        while queue:
            cur = queue.pop(0)
            if cur in seen:
                continue
            seen.add(cur)
            result.append(cur)
            queue.extend(self._children.get(cur, []))
        return result

    def orphans(self) -> list[str]:
        """Events whose parent_message_id is absent from this set, insertion order."""
        return [e["message_id"] for e in self._events if e["message_id"] in self._orphan_set]

    def traversal_order(self) -> list[str]:
        """All transcript event IDs in canonical insertion order."""
        return [e["message_id"] for e in self._events]

    # ── summary ───────────────────────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        """JSON-safe deterministic topology summary."""
        return {
            "event_count": len(self._events),
            "root_count": len(self.roots()),
            "orphan_count": len(self._orphan_set),
            "roots": self.roots(),
            "orphans": self.orphans(),
            "traversal_order": self.traversal_order(),
            "depth_map": {
                e["message_id"]: self.depth(e["message_id"])
                for e in self._events
            },
        }
