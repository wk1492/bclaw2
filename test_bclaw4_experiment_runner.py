"""
BCLAW4 Experiment 001 — 10-move ledgered autonomy trial.
Branch: bclaw4-chaos-lab-001.
"""
from bclaw4_experiment_runner import RUN_ID, run_bclaw4_experiment


def _result():
    return run_bclaw4_experiment()


# 1. All required top-level keys present
def test_required_keys():
    r = _result()
    for key in ("summary_id", "run_id", "ledger_path", "move_count",
                "move_ids", "message_ids", "topology", "chain_ok", "replay_count"):
        assert key in r, f"missing key: {key}"


# 2. Exactly 10 moves emitted
def test_move_count_is_ten():
    r = _result()
    assert r["move_count"] == 10
    assert len(r["move_ids"]) == 10
    assert len(r["message_ids"]) == 10


# 3. Move IDs are m01..m10 in order
def test_move_ids_in_order():
    r = _result()
    assert r["move_ids"] == [f"m{i:02d}" for i in range(1, 11)]


# 4. Ledger chain is valid after all appends
def test_chain_ok():
    r = _result()
    assert r["chain_ok"] is True


# 5. Replay returns exactly 10 transcript events
def test_replay_count_matches_move_count():
    r = _result()
    assert r["replay_count"] == 10


# 6. Topology has 10 nodes, 0 orphaned
def test_topology_node_count_and_no_orphans():
    r = _result()
    assert r["topology"]["node_count"] == 10
    assert r["topology"]["orphaned"] == []


# 7. topology_hash is a 64-char hex string
def test_topology_hash_is_hex64():
    r = _result()
    h = r["topology"]["topology_hash"]
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


# 8. summary_id is deterministic across runs
def test_summary_id_deterministic():
    assert _result()["summary_id"] == _result()["summary_id"]


# 9. All emitted message_ids belong to run RUN_ID
def test_all_messages_belong_to_run():
    from transcript_ledger import load_ledger_lines
    r = _result()
    records = load_ledger_lines(r["ledger_path"])
    transcript = [rec for rec in records if rec.get("event_type") == "transcript.message"]
    for rec in transcript:
        assert rec["run_id"] == RUN_ID, f"wrong run_id in {rec['message_id']}"


# 10. Arbiter moves appear after all events they reference in linearized order
def test_arbiter_moves_after_all_references():
    from transcript_ledger import load_ledger_lines
    from transcript_topology import linearize_transcript_topology

    r = _result()
    records = load_ledger_lines(r["ledger_path"])
    events = [rec for rec in records if rec.get("event_type") == "transcript.message"]
    linearized = linearize_transcript_topology(events)
    order = [e["message_id"] for e in linearized]
    by_id = {e["message_id"]: e for e in linearized}

    for event in linearized:
        if event["role"] != "arbiter":
            continue
        arb_pos = order.index(event["message_id"])
        for ref_id in event.get("references", []):
            assert order.index(ref_id) < arb_pos, (
                f"reference {ref_id} must precede arbiter {event['message_id']}"
            )
