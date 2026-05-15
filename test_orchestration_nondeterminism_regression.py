"""
Nondeterminism regression tests — deterministic orchestration audit.
Branch: task2-orchestrator-lockdown.

Each test is labeled EXPECTED_PASS or EXPECTED_FAIL.
EXPECTED_FAIL tests prove current nondeterminism bugs found in the audit.
EXPECTED_PASS tests confirm safe-path invariants that must be preserved.
No production code is modified by any test in this file.
"""
import json
import os
import tempfile
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 1: Replay determinism
# (audit findings C3 — wall-clock timestamp in hashed records)
# ═══════════════════════════════════════════════════════════════════════════════

def test_build_run_record_hash_is_stable_with_fixed_timestamp():
    """
    Risk guarded: execution_ledger.py:26 — datetime.now(UTC) default in build_run_record.
    Deterministic invariant: same logical record + same explicit timestamp → same hash on every run.
    Expected failure mode: test fails if hash changes across identical calls → replay impossible.
    Why this matters for replay correctness: event_hash and rolling_hash embed the hash;
        if hash is nondeterministic, verify_ledger fails on every replay after the first run.
    EXPECTED_PASS: safe path — caller supplies explicit timestamp.
    """
    from execution_ledger import build_run_record

    kwargs = dict(
        run_type="audit_test",
        input_data={"x": 1},
        output_data={"y": 2},
        timestamp="2026-01-01T00:00:00+00:00",
    )
    r1 = build_run_record(**kwargs)
    r2 = build_run_record(**kwargs)
    assert r1["hash"] == r2["hash"]
    assert r1["timestamp"] == r2["timestamp"]


def test_build_run_record_hash_encodes_timestamp():
    """
    Risk guarded: execution_ledger.py:26 — timestamp is included in hash_record_payload input.
    Deterministic invariant: any change in timestamp must change the hash.
    Expected failure mode: test fails if hash ignores timestamp → incorrect replay verification.
    Why this matters for replay correctness: callers that do not supply a timestamp get
        datetime.now(UTC), which changes every run → different hash every run →
        rolling_hash and event_id diverge across replay runs → verify_ledger rejects every event.
    EXPECTED_PASS: confirms timestamp is in hash (documents why wall-clock default is unsafe).
    """
    from execution_ledger import build_run_record

    r1 = build_run_record("t", {"x": 1}, {"y": 2}, timestamp="2026-01-01T00:00:00+00:00")
    r2 = build_run_record("t", {"x": 1}, {"y": 2}, timestamp="2026-01-01T00:00:01+00:00")
    assert r1["hash"] != r2["hash"], (
        "timestamp is embedded in the hash — wall-clock default makes hash nondeterministic"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 2: Ledger append ordering
# (audit finding C1 — append_run missing separators=(',',':'))
# ═══════════════════════════════════════════════════════════════════════════════

def test_append_run_on_disk_bytes_are_canonical():
    """
    Risk guarded: execution_ledger.py:38 — json.dumps(record, sort_keys=True) without separators.
    Deterministic invariant: every line written by append_run must equal canonical_json(record).
    Expected failure mode: on-disk bytes contain spaces after ':' and ',' but canonical form does not
        → re-hashing the on-disk line produces a different hash than the stored 'hash' field.
    Why this matters for replay correctness: any audit tool that reads execution_ledger.jsonl and
        recomputes the hash from the on-disk bytes will find a mismatch → verification fails.
    EXPECTED_FAIL: proves current bug — append_run writes non-canonical bytes.
    """
    import execution_ledger as el
    from execution_ledger import build_run_record, canonical_json

    record = build_run_record(
        "audit_test", {"in": 1}, {"out": 2},
        timestamp="2026-01-01T00:00:00+00:00",
    )
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    orig = el.EXECUTION_LEDGER_FILE
    el.EXECUTION_LEDGER_FILE = Path(path)
    try:
        el.append_run(record)
        on_disk = Path(path).read_text().strip()
        expected = canonical_json(record)
        assert on_disk == expected, (
            f"append_run wrote non-canonical bytes (separators missing).\n"
            f"  on-disk:   {on_disk[:120]!r}\n"
            f"  canonical: {expected[:120]!r}"
        )
    finally:
        el.EXECUTION_LEDGER_FILE = orig
        os.unlink(path)


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 3: Arbitration ordering
# (audit finding M1 — fusion.py keep_last iterates seen.values() unsorted)
# ═══════════════════════════════════════════════════════════════════════════════

def test_fusion_keep_last_output_order_stable_across_input_permutations():
    """
    Risk guarded: fusion.py:14 — keep_last iterates seen.values() in dict insertion order.
    Deterministic invariant: keep_last output id-order must be identical regardless of input
        arrival order (same logical records, different sequence).
    Expected failure mode: ids_ab != ids_ba → output order is input-arrival-dependent.
    Why this matters for replay correctness: orchestrator.py compare_strategies checks
        first_out != last_out by value equality; if keep_last output order varies with input
        order, strategies_differ flips nondeterministically → arbitration decisions are wrong.
    EXPECTED_FAIL: proves current bug — A-first vs B-first inputs produce different output order.
    """
    from fusion import fuse

    # Same logical content, different arrival order
    records_a_first = [{"id": "A", "v": 1}, {"id": "B", "v": 2}, {"id": "A", "v": 99}]
    records_b_first = [{"id": "B", "v": 2}, {"id": "A", "v": 1}, {"id": "A", "v": 99}]

    ids_ab = [r["id"] for r in fuse(records_a_first, strategy="keep_last")]
    ids_ba = [r["id"] for r in fuse(records_b_first, strategy="keep_last")]

    assert ids_ab == ids_ba, (
        f"keep_last output order is input-arrival-order-dependent.\n"
        f"  A-first input → output order: {ids_ab}\n"
        f"  B-first input → output order: {ids_ba}"
    )


def test_fusion_keep_first_output_order_is_stable():
    """
    Risk guarded: None — keep_first is the safe reference baseline.
    Deterministic invariant: keep_first preserves first-seen order deterministically.
    Expected failure mode: test fails if keep_first order changes → would be a regression.
    Why this matters for replay correctness: keep_first is the current safe strategy;
        confirming stability here isolates keep_last as the only ordering risk.
    EXPECTED_PASS: confirms keep_first is the stable arbitration baseline.
    """
    from fusion import fuse

    records = [{"id": "A", "v": 1}, {"id": "B", "v": 2}, {"id": "A", "v": 99}]
    out1 = [r["id"] for r in fuse(records, strategy="keep_first")]
    out2 = [r["id"] for r in fuse(records, strategy="keep_first")]
    assert out1 == out2 == ["A", "B"]


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 4: Filesystem traversal stability
# (audit finding M2 — clear_inbox/clear_outbox use unsorted glob)
# ═══════════════════════════════════════════════════════════════════════════════

def test_message_bus_get_inbox_returns_sorted_by_turn_number():
    """
    Risk guarded: message_bus.py:61-62 — clear_inbox iterates inbox.glob('*.json') unsorted.
    Deterministic invariant: get_inbox must return messages in deterministic turn_number order
        regardless of filesystem insertion order.
    Expected failure mode: turns != [0, 1, 2] → read path is not sorted → replay sequence differs.
    Why this matters for replay correctness: a crash during clear_inbox leaves the inbox in a
        FS-order-dependent partial state; get_inbox reads the remainder in sorted filename order,
        but which files remain depends on the FS deletion sequence, not the logical message order.
        This test confirms the read path is sorted — isolating clear_inbox as the failure surface.
    EXPECTED_PASS: confirms get_inbox read path is already deterministically sorted.
    """
    from message_bus import put_inbox, get_inbox, clear_inbox

    wid = "test_audit_nondeterminism_worker_01"
    clear_inbox(wid)

    for turn in [2, 0, 1]:  # insert out of turn order
        put_inbox({
            "message_id": f"msg_turn{turn}_auditnd01",
            "candidate_id": "c_audit_nd",
            "sender": "audit_nd_test",
            "recipient": wid,
            "role": "user",
            "turn_number": turn,
            "payload": {"text": f"turn {turn}"},
        })

    msgs = get_inbox(wid)
    turns = [m["turn_number"] for m in msgs]
    assert turns == [0, 1, 2], (
        f"get_inbox must return messages sorted by turn_number; got {turns}"
    )
    clear_inbox(wid)


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 5: Serialization canonicalization
# (audit findings C2 and C4)
# ═══════════════════════════════════════════════════════════════════════════════

def test_safe_patcher_log_entry_is_canonical():
    """
    Risk guarded: safe_patcher.py:112 — json.dumps(entry) with no sort_keys, no separators.
    Deterministic invariant: every line written to idea_ledger.jsonl must be canonical JSON
        (sort_keys=True, separators=(',',':'), ensure_ascii=False).
    Expected failure mode: raw_line != canonical → key order and spacing are insertion-order-
        dependent; byte-level patch provenance comparison fails.
    Why this matters for replay correctness: patch log entries in idea_ledger.jsonl are not
        hash-chained; without canonical serialization they cannot be deterministically re-verified.
        A future hash-chain covering patch entries would produce different hashes across runs.
    EXPECTED_FAIL: proves _log_patch writes non-canonical JSON (wrong key order + extra spaces).
    """
    from safe_patcher import SafePatcher

    with tempfile.TemporaryDirectory() as tmp:
        patcher = SafePatcher()
        patcher.root = Path(tmp).resolve()

        patch = {"patch_id": "audit_nd_p1", "candidate_id": "audit_nd_c1", "files": []}
        applied = [{
            "path": "x.json",
            "absolute_path": str(Path(tmp) / "x.json"),
            "before_hash": "aa" * 32,
            "after_hash": "bb" * 32,
            "changed": False,
        }]
        patcher._log_patch(patch, applied, dry_run=True)

        ledger = Path(tmp) / "idea_ledger.jsonl"
        raw_line = ledger.read_text().strip()
        parsed = json.loads(raw_line)
        canonical = json.dumps(
            parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )

        assert raw_line == canonical, (
            f"_log_patch wrote non-canonical JSON.\n"
            f"  on-disk:   {raw_line[:120]!r}\n"
            f"  canonical: {canonical[:120]!r}"
        )


def test_generate_candidates_ids_embed_wall_clock_date():
    """
    Risk guarded: generate_candidates.py:5 — base_date = datetime.now(UTC).strftime('%Y%m%d').
    Deterministic invariant: candidate IDs must not embed wall-clock dates;
        same candidate template must produce same ID on every run regardless of calendar date.
    Expected failure mode: test passes (confirming IDs DO contain today's date) → this is the bug;
        on a different calendar date, IDs will differ → all ledger cross-references become dangling.
    Why this matters for replay correctness: any ledger entry, critique result, or validation
        record that references a candidate by ID will reference a date-stamped ID that does not
        exist when the ledger is replayed on a different date.
    EXPECTED_PASS: asserts IDs contain today's date — confirms wall-clock embedding is active.
    """
    from datetime import datetime, timezone
    import generate_candidates as gc

    candidates = gc.generate_new_candidates()
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    for c in candidates:
        assert today in c["id"], (
            f"Candidate ID {c['id']!r} does not embed today's date {today!r}. "
            f"If this assertion fails, the wall-clock embedding has already been removed — "
            f"update this test to verify content-addressed IDs instead."
        )
