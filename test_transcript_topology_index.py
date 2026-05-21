"""
test_transcript_topology_index.py

Unit tests for TranscriptTopologyIndex.
No model calls. No ledger I/O. No schema changes.
"""
from __future__ import annotations

import json

import pytest

from transcript_topology_index import TranscriptTopologyIndex

# ── fixture ────────────────────────────────────────────────────────────────────

def _evt(mid, parent=None, role="proposal"):
    e = {"event_type": "transcript.message", "message_id": mid, "role": role}
    if parent:
        e["parent_message_id"] = parent
    return e


def _make_tree():
    """
    root
    ├── child_a  (sibling 1)
    │   └── grandchild
    └── child_b  (sibling 2)
    """
    root       = _evt("root")
    child_a    = _evt("child_a",    parent="root",    role="critique")
    child_b    = _evt("child_b",    parent="root",    role="critique")
    grandchild = _evt("grandchild", parent="child_a", role="critique")
    return [root, child_a, child_b, grandchild]


# ── 1. Single root ─────────────────────────────────────────────────────────────

def test_single_root_traversal():
    idx = TranscriptTopologyIndex([_evt("only")])
    assert idx.roots() == ["only"]
    assert idx.traversal_order() == ["only"]
    assert idx.depth("only") == 0


# ── 2. Parent before child (depth) ────────────────────────────────────────────

def test_parent_depth_less_than_child():
    idx = TranscriptTopologyIndex(_make_tree())
    assert idx.depth("root") == 0
    assert idx.depth("child_a") == 1
    assert idx.depth("grandchild") == 2


def test_ancestors_root_to_leaf():
    idx = TranscriptTopologyIndex(_make_tree())
    assert idx.ancestors("grandchild") == ["child_a", "root"]
    assert idx.ancestors("child_a") == ["root"]
    assert idx.ancestors("root") == []


# ── 3. Siblings ordered by insertion order (not message_id, not timestamp) ────

def test_siblings_insertion_order():
    # child_b inserted before child_a — ordering must reflect that
    root    = _evt("root")
    child_b = _evt("zz_child_b", parent="root", role="critique")  # lexically later
    child_a = _evt("aa_child_a", parent="root", role="critique")  # lexically earlier
    idx = TranscriptTopologyIndex([root, child_b, child_a])
    # children must be in insertion order: child_b first, then child_a
    assert idx.children("root") == ["zz_child_b", "aa_child_a"]
    assert idx.siblings("zz_child_b") == ["aa_child_a"]
    assert idx.siblings("aa_child_a") == ["zz_child_b"]


# ── 4. Execution events ignored ───────────────────────────────────────────────

def test_non_transcript_events_ignored():
    events = [
        {"event_type": "model_call_record", "message_id": "gate_1"},
        _evt("root"),
        {"event_type": "routing_decision_record"},
        _evt("child_a", parent="root"),
    ]
    idx = TranscriptTopologyIndex(events)
    assert idx.traversal_order() == ["root", "child_a"]
    assert "gate_1" not in idx.traversal_order()


# ── 5. Repeated runs byte-identical ───────────────────────────────────────────

def test_summary_byte_identical_repeated():
    events = _make_tree()
    s1 = json.dumps(TranscriptTopologyIndex(events).summary(),
                    sort_keys=True, separators=(",", ":"))
    s2 = json.dumps(TranscriptTopologyIndex(events).summary(),
                    sort_keys=True, separators=(",", ":"))
    assert s1 == s2


# ── 6. Branching critique tree order stable ───────────────────────────────────

def test_branching_tree_traversal_stable():
    events = _make_tree()
    idx = TranscriptTopologyIndex(events)
    order = idx.traversal_order()
    assert order == ["root", "child_a", "child_b", "grandchild"]
    assert idx.children("root") == ["child_a", "child_b"]
    assert idx.children("child_a") == ["grandchild"]
    assert idx.children("child_b") == []
    assert idx.descendants("root") == ["child_a", "child_b", "grandchild"]


def test_descendants_bfs_insertion_order():
    idx = TranscriptTopologyIndex(_make_tree())
    # BFS from root: child_a, child_b, then grandchild
    assert idx.descendants("root") == ["child_a", "child_b", "grandchild"]


# ── 7. Missing parent → orphan, deterministic ────────────────────────────────

def test_missing_parent_detected_as_orphan():
    orphan = _evt("orphan", parent="nonexistent_parent")
    idx = TranscriptTopologyIndex([_evt("root"), orphan])
    assert "orphan" in idx.orphans()
    assert "orphan" not in idx.roots()
    assert "orphan" in idx.traversal_order()  # still present in traversal


def test_orphan_detection_deterministic():
    events = [_evt("root"), _evt("orphan", parent="ghost")]
    o1 = TranscriptTopologyIndex(events).orphans()
    o2 = TranscriptTopologyIndex(events).orphans()
    assert o1 == o2 == ["orphan"]


def test_orphan_not_in_roots():
    idx = TranscriptTopologyIndex([
        _evt("root"),
        _evt("orphan", parent="ghost"),
    ])
    assert idx.roots() == ["root"]
    assert not idx.is_root("orphan")


# ── 8. Canonical serialization preserved ─────────────────────────────────────

def test_summary_json_safe():
    idx = TranscriptTopologyIndex(_make_tree())
    s = idx.summary()
    serialized = json.dumps(s, sort_keys=True, separators=(",", ":"))
    assert json.loads(serialized) == s


def test_summary_keys_present():
    idx = TranscriptTopologyIndex(_make_tree())
    s = idx.summary()
    for key in ("event_count", "root_count", "orphan_count",
                "roots", "orphans", "traversal_order", "depth_map"):
        assert key in s


# ── Input not mutated ─────────────────────────────────────────────────────────

def test_input_events_not_mutated():
    events = _make_tree()
    originals = [dict(e) for e in events]
    TranscriptTopologyIndex(events)
    for original, after in zip(originals, events):
        assert original == after
