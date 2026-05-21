"""
test_transcript_fingerprint.py

Unit tests for transcript_fingerprint module.
No model calls. No ledger I/O. No schema changes.
"""
from __future__ import annotations

from transcript_fingerprint import compute_topology_fingerprint, fingerprint_report

_TS = "transcript.message"


def _evt(mid, parent=None, role="proposal", extra=None):
    e = {"event_type": _TS, "message_id": mid, "role": role}
    if parent:
        e["parent_message_id"] = parent
    if extra:
        e.update(extra)
    return e


def _gate(mid):
    return {"event_type": "model_call_record", "message_id": mid}


# ── 1. Same graph, different ingestion order → identical fingerprint ───────────

def test_ingestion_order_independent():
    events = [_evt("root"), _evt("child_a", parent="root"), _evt("child_b", parent="root")]
    fp1 = compute_topology_fingerprint(events)
    fp2 = compute_topology_fingerprint(list(reversed(events)))
    assert fp1 == fp2


def test_all_permutations_identical():
    import itertools
    events = [_evt("root"), _evt("child", parent="root"), _evt("grandchild", parent="child")]
    fingerprints = {
        compute_topology_fingerprint(list(perm))
        for perm in itertools.permutations(events)
    }
    assert len(fingerprints) == 1


# ── 2. Different sibling order inputs → identical fingerprint ─────────────────

def test_sibling_order_independent():
    root = _evt("root")
    # message_id bytes determine sibling order in linearizer
    # fingerprint must be the same regardless of which sibling appears first in input
    sib_a = _evt("tmsg_aaaa", parent="root")
    sib_b = _evt("tmsg_bbbb", parent="root")
    fp1 = compute_topology_fingerprint([root, sib_a, sib_b])
    fp2 = compute_topology_fingerprint([root, sib_b, sib_a])
    assert fp1 == fp2


# ── 3. Structurally different trees → different fingerprint ───────────────────

def test_different_structure_different_fingerprint():
    # Linear chain
    chain = [_evt("root"), _evt("child", parent="root")]
    # Same nodes, child is root (no parent)
    flat = [_evt("root"), _evt("child")]
    assert compute_topology_fingerprint(chain) != compute_topology_fingerprint(flat)


def test_extra_node_different_fingerprint():
    base = [_evt("root"), _evt("child", parent="root")]
    extended = base + [_evt("grandchild", parent="child")]
    assert compute_topology_fingerprint(base) != compute_topology_fingerprint(extended)


# ── 4. Execution events ignored ───────────────────────────────────────────────

def test_execution_events_ignored():
    transcript = [_evt("root"), _evt("child", parent="root")]
    mixed = [_gate("gate_1")] + transcript + [_gate("gate_2")]
    assert compute_topology_fingerprint(transcript) == compute_topology_fingerprint(mixed)


# ── 5. Metadata changes do not affect fingerprint ────────────────────────────

def test_metadata_irrelevant():
    base = [_evt("root"), _evt("child", parent="root")]
    with_meta = [
        _evt("root", extra={"content": "abc", "sender": "agent_x", "created_at": "2026-01-01"}),
        _evt("child", parent="root", extra={"content": "xyz", "role": "critique"}),
    ]
    assert compute_topology_fingerprint(base) == compute_topology_fingerprint(with_meta)


# ── 6. Repeated runs byte-identical ──────────────────────────────────────────

def test_repeated_runs_identical():
    events = [_evt("root"), _evt("child_a", parent="root"), _evt("child_b", parent="root")]
    results = {compute_topology_fingerprint(events) for _ in range(5)}
    assert len(results) == 1


def test_fingerprint_is_64_char_hex():
    fp = compute_topology_fingerprint([_evt("root")])
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


# ── 7. Orphan handling deterministic ─────────────────────────────────────────

def test_orphan_fingerprint_deterministic():
    events = [_evt("root"), _evt("orphan", parent="nonexistent")]
    fp1 = compute_topology_fingerprint(events)
    fp2 = compute_topology_fingerprint(events)
    assert fp1 == fp2


def test_orphan_vs_root_different_fingerprint():
    with_orphan = [_evt("root"), _evt("orphan", parent="ghost")]
    two_roots = [_evt("root"), _evt("orphan")]
    assert compute_topology_fingerprint(with_orphan) != compute_topology_fingerprint(two_roots)


# ── 8. Inputs not mutated ────────────────────────────────────────────────────

def test_inputs_not_mutated():
    events = [_evt("root"), _evt("child", parent="root")]
    originals = [dict(e) for e in events]
    compute_topology_fingerprint(events)
    for orig, after in zip(originals, events):
        assert orig == after


# ── fingerprint_report ────────────────────────────────────────────────────────

def test_report_keys_present():
    report = fingerprint_report([_evt("root"), _evt("child", parent="root")])
    assert set(report) == {"fingerprint", "node_count", "root_count"}
    assert report["node_count"] == 2
    assert report["root_count"] == 1
    assert len(report["fingerprint"]) == 64
