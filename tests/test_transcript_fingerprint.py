"""
tests/test_transcript_fingerprint.py — TASK-20260520-TRANSCRIPT-FINGERPRINT-V1

Canonical ordering authority: transcript_topology.linearize_transcript_topology
Missing parent normalization: None (→ JSON null)
No topology traversal logic duplicated here.
"""
from __future__ import annotations

import copy

from transcript_fingerprint import compute_topology_fingerprint

_TS = "transcript.message"


def _evt(mid, parent=None):
    e = {"event_type": _TS, "message_id": mid}
    if parent:
        e["parent_message_id"] = parent
    return e


# ── 1. identical_inputs_same_hash ─────────────────────────────────────────────

def test_identical_inputs_same_hash():
    events = [_evt("tmsg_root"), _evt("tmsg_child", parent="tmsg_root")]
    assert compute_topology_fingerprint(events) == compute_topology_fingerprint(events)


# ── 2. reordered_input_same_hash ──────────────────────────────────────────────

def test_reordered_input_same_hash():
    root  = _evt("tmsg_root")
    child = _evt("tmsg_child", parent="tmsg_root")
    grand = _evt("tmsg_grand", parent="tmsg_child")
    fp1 = compute_topology_fingerprint([root, child, grand])
    fp2 = compute_topology_fingerprint([grand, child, root])
    fp3 = compute_topology_fingerprint([child, grand, root])
    assert fp1 == fp2 == fp3


# ── 3. parent_child_change_changes_hash ───────────────────────────────────────

def test_parent_child_change_changes_hash():
    chain = [_evt("tmsg_root"), _evt("tmsg_child", parent="tmsg_root")]
    flat  = [_evt("tmsg_root"), _evt("tmsg_child")]
    assert compute_topology_fingerprint(chain) != compute_topology_fingerprint(flat)


# ── 4. orphan_structure_changes_hash ─────────────────────────────────────────

def test_orphan_structure_changes_hash():
    with_orphan = [_evt("tmsg_root"), _evt("tmsg_x", parent="tmsg_ghost")]
    two_roots   = [_evt("tmsg_root"), _evt("tmsg_x")]
    assert compute_topology_fingerprint(with_orphan) != compute_topology_fingerprint(two_roots)


# ── 5. empty_transcript_stable_hash ──────────────────────────────────────────

def test_empty_transcript_stable_hash():
    fp1 = compute_topology_fingerprint([])
    fp2 = compute_topology_fingerprint([])
    assert fp1 == fp2
    assert len(fp1) == 64
    assert all(c in "0123456789abcdef" for c in fp1)


def test_empty_vs_nonempty_differ():
    assert compute_topology_fingerprint([]) != compute_topology_fingerprint([_evt("tmsg_root")])


# ── 6. non_message_events_ignored ────────────────────────────────────────────

def test_non_message_events_ignored():
    transcript = [_evt("tmsg_root"), _evt("tmsg_child", parent="tmsg_root")]
    mixed = [
        {"event_type": "model_call_record", "message_id": "gate_1"},
        transcript[0],
        {"event_type": "routing_decision_record"},
        transcript[1],
        {"event_type": "model_output_record", "run_id": "r1"},
    ]
    assert compute_topology_fingerprint(transcript) == compute_topology_fingerprint(mixed)


# ── 7. repeated_calls_identical ──────────────────────────────────────────────

def test_repeated_calls_identical():
    events = [_evt("tmsg_root"), _evt("tmsg_a", parent="tmsg_root"), _evt("tmsg_b", parent="tmsg_root")]
    results = [compute_topology_fingerprint(events) for _ in range(10)]
    assert len(set(results)) == 1


# ── 8. deepcopy_inputs_identical ─────────────────────────────────────────────

def test_deepcopy_inputs_identical():
    events = [_evt("tmsg_root"), _evt("tmsg_child", parent="tmsg_root")]
    fp1 = compute_topology_fingerprint(events)
    fp2 = compute_topology_fingerprint(copy.deepcopy(events))
    assert fp1 == fp2


def test_inputs_not_mutated():
    events = [_evt("tmsg_root"), _evt("tmsg_child", parent="tmsg_root")]
    originals = copy.deepcopy(events)
    compute_topology_fingerprint(events)
    assert events == originals


# ── 9. unicode_message_ids_stable ────────────────────────────────────────────

def test_unicode_message_ids_stable():
    events = [
        {"event_type": _TS, "message_id": "tmsg_中文"},
        {"event_type": _TS, "message_id": "tmsg_élève",
         "parent_message_id": "tmsg_中文"},
    ]
    fp1 = compute_topology_fingerprint(events)
    fp2 = compute_topology_fingerprint(list(reversed(events)))
    assert fp1 == fp2
    assert len(fp1) == 64


# ── Canonical ordering inherited from transcript_topology (not duplicated) ────

def test_canonical_ordering_from_topology():
    """Fingerprint uses linearize_transcript_topology as sole ordering authority."""
    from transcript_topology import linearize_transcript_topology
    events = [
        _evt("tmsg_zzz", parent="tmsg_aaa"),
        _evt("tmsg_aaa"),
    ]
    linearized = linearize_transcript_topology(list(events))
    # Root (tmsg_aaa) must come first in linearization → in fingerprint payload
    assert linearized[0]["message_id"] == "tmsg_aaa"
    # Fingerprint is stable for this ordering
    assert compute_topology_fingerprint(events) == compute_topology_fingerprint(list(reversed(events)))


# ── Stable hash examples ──────────────────────────────────────────────────────
# These assert structural identity without hardcoding fragile values.
# Rerun to regenerate if algorithm changes (requires baseline update + review).

def test_linear_chain_stable():
    chain = [
        _evt("tmsg_root"),
        _evt("tmsg_child", parent="tmsg_root"),
        _evt("tmsg_grand", parent="tmsg_child"),
    ]
    fp = compute_topology_fingerprint(chain)
    assert fp == compute_topology_fingerprint(list(reversed(chain)))
    assert fp == "e372cde693f5625272627f57e13d368ba9aeecc8a3b472d75f22b38e53243d7b"


def test_branching_critique_graph_stable():
    branch = [
        _evt("tmsg_root"),
        _evt("tmsg_a", parent="tmsg_root"),
        _evt("tmsg_b", parent="tmsg_root"),
        _evt("tmsg_c", parent="tmsg_a"),
    ]
    fp = compute_topology_fingerprint(branch)
    assert fp == compute_topology_fingerprint(list(reversed(branch)))
    assert fp == "0299d56f269c2c86ff9fc3cd543273a4c77ace6a5108f54be78cd8e89a8b436b"


# ── Additional V2 tests ───────────────────────────────────────────────────────

def test_branching_change_changes_hash():
    """Moving a node to a different parent changes the fingerprint."""
    base   = [_evt("r"), _evt("a", parent="r"), _evt("b", parent="r")]
    moved  = [_evt("r"), _evt("a", parent="r"), _evt("b", parent="a")]
    assert compute_topology_fingerprint(base) != compute_topology_fingerprint(moved)


def test_root_change_changes_hash():
    """Different root id → different fingerprint."""
    g1 = [_evt("tmsg_root1"), _evt("tmsg_child", parent="tmsg_root1")]
    g2 = [_evt("tmsg_root2"), _evt("tmsg_child", parent="tmsg_root2")]
    assert compute_topology_fingerprint(g1) != compute_topology_fingerprint(g2)


def test_mixed_event_stream_stable():
    """Mixed execution + transcript stream produces same hash as transcript-only."""
    transcript = [_evt("tmsg_r"), _evt("tmsg_c", parent="tmsg_r")]
    mixed = [
        {"event_type": "model_call_record", "run_id": "x"},
        transcript[0],
        {"event_type": "routing_decision_record"},
        transcript[1],
        {"event_type": "model_output_record", "run_id": "x"},
    ]
    assert compute_topology_fingerprint(transcript) == compute_topology_fingerprint(mixed)


def test_unicode_parent_ids_stable():
    """Unicode in parent_message_id is preserved exactly."""
    events = [
        {"event_type": _TS, "message_id": "tmsg_中文"},
        {"event_type": _TS, "message_id": "tmsg_child", "parent_message_id": "tmsg_中文"},
    ]
    fp1 = compute_topology_fingerprint(events)
    fp2 = compute_topology_fingerprint(list(reversed(events)))
    assert fp1 == fp2


def test_missing_parent_normalizes_to_null():
    """Absent key, None value, and empty string all normalize to null."""
    no_key   = [{"event_type": _TS, "message_id": "tmsg_r"}]
    none_val = [{"event_type": _TS, "message_id": "tmsg_r", "parent_message_id": None}]
    empty    = [{"event_type": _TS, "message_id": "tmsg_r", "parent_message_id": ""}]
    fp = compute_topology_fingerprint(no_key)
    assert compute_topology_fingerprint(none_val) == fp
    assert compute_topology_fingerprint(empty) == fp


def test_replay_permutation_stability():
    """All 6 permutations of a 3-node chain produce the same fingerprint."""
    import itertools
    events = [_evt("tmsg_r"), _evt("tmsg_a", parent="tmsg_r"), _evt("tmsg_b", parent="tmsg_a")]
    fps = {compute_topology_fingerprint(list(p)) for p in itertools.permutations(events)}
    assert len(fps) == 1


def test_insertion_order_independence():
    """Insertion-order independence verified via fixture graphs."""
    from tests.fixtures.transcript_graphs import linear_chain, EXPECTED_HASHES
    assert compute_topology_fingerprint(linear_chain()) == EXPECTED_HASHES["linear_chain"]
    assert compute_topology_fingerprint(list(reversed(linear_chain()))) == EXPECTED_HASHES["linear_chain"]


def test_orphan_linearization_matches_topology():
    """Orphan tuple preserves the dangling parent_message_id value, not null."""
    from transcript_topology import linearize_transcript_topology
    events = [_evt("tmsg_root"), _evt("tmsg_orphan", parent="tmsg_ghost")]
    linearized = linearize_transcript_topology(list(events))
    orphan_evt = next(e for e in linearized if e["message_id"] == "tmsg_orphan")
    assert orphan_evt.get("parent_message_id") == "tmsg_ghost"  # topology preserves it
    # Fingerprint uses same value
    fp = compute_topology_fingerprint(events)
    assert fp == "63ce393f5ae3be02c473111c7c9ce4980cc1ce69b056fe941c23f93cbba3e86a"
