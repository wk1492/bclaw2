"""
End-to-end tests covering Tasks 2-9.
Run: python3 test_end_to_end.py
"""
import json
import shutil
import tempfile
from pathlib import Path


# ── helpers ──────────────────────────────────────────────────────────────────

def _tmp_dir():
    return Path(tempfile.mkdtemp())


# ── Task 2: deterministic message ID ─────────────────────────────────────────

def test_deterministic_message_id():
    from deterministic_message_id import generate_message_id

    a = generate_message_id("cand-001", "loop", "worker_a", "user", 0)
    b = generate_message_id("cand-001", "loop", "worker_a", "user", 0)
    assert a == b, "same inputs must produce same ID"
    assert a.startswith("msg_")
    assert len(a) == 68  # msg_ + 64 hex

    c = generate_message_id("cand-001", "loop", "worker_a", "user", 1)
    assert a != c, "different turn_number must produce different ID"
    print("PASS: deterministic_message_id")


# ── Task 3: message_bus inbox/outbox ─────────────────────────────────────────

def test_worker_inbox_outbox():
    import message_bus as mb
    from deterministic_message_id import generate_message_id

    orig_inbox = mb.INBOX_DIR
    orig_outbox = mb.OUTBOX_DIR
    tmp = _tmp_dir()
    mb.INBOX_DIR = tmp / "inbox"
    mb.OUTBOX_DIR = tmp / "outbox"

    try:
        mid = generate_message_id("cand-x", "loop", "worker_a", "user", 0)
        msg = {
            "message_id": mid,
            "candidate_id": "cand-x",
            "sender": "loop",
            "recipient": "worker_a",
            "role": "user",
            "turn_number": 0,
            "payload": {"text": "hello"},
        }
        mb.put_inbox(msg)
        received = mb.get_inbox("worker_a")
        assert len(received) == 1
        assert received[0]["message_id"] == mid

        reply_id = generate_message_id("cand-x", "worker_a", "loop", "assistant", 1)
        reply = {
            "message_id": reply_id,
            "candidate_id": "cand-x",
            "sender": "worker_a",
            "recipient": "loop",
            "role": "assistant",
            "turn_number": 1,
            "payload": {"text": "world"},
        }
        mb.put_outbox(reply)
        sent = mb.get_outbox("worker_a")
        assert len(sent) == 1
        assert sent[0]["message_id"] == reply_id

        mb.clear_inbox("worker_a")
        assert mb.get_inbox("worker_a") == []
        mb.clear_outbox("worker_a")
        assert mb.get_outbox("worker_a") == []
        print("PASS: worker_inbox_outbox")
    finally:
        mb.INBOX_DIR = orig_inbox
        mb.OUTBOX_DIR = orig_outbox
        shutil.rmtree(tmp, ignore_errors=True)


# ── Task 3: transcript hash ───────────────────────────────────────────────────

def test_transcript_hash():
    from transcript import build_transcript, get_transcript_hash
    from deterministic_message_id import generate_message_id

    mid = generate_message_id("cand-t", "loop", "worker_a", "user", 0)
    turns = [
        {
            "message_id": mid,
            "candidate_id": "cand-t",
            "sender": "loop",
            "recipient": "worker_a",
            "role": "user",
            "turn_number": 0,
            "payload": {"text": "test prompt"},
        }
    ]
    t1 = build_transcript("cand-t", turns)
    t2 = build_transcript("cand-t", turns)
    assert t1["transcript_hash"] == t2["transcript_hash"], "same turns must produce same hash"
    assert get_transcript_hash(t1) == t1["transcript_hash"]
    assert t1["transcript_id"].startswith("txn_")
    print("PASS: transcript_hash")


# ── Task 7: transcript replay validator ──────────────────────────────────────

def test_transcript_replay_validator():
    from transcript import build_transcript
    from transcript_replay_validator import verify_transcript_hash, compare_transcripts
    from deterministic_message_id import generate_message_id

    mid = generate_message_id("cand-rv", "loop", "w", "user", 0)
    turns = [
        {
            "message_id": mid,
            "candidate_id": "cand-rv",
            "sender": "loop",
            "recipient": "w",
            "role": "user",
            "turn_number": 0,
            "payload": {"text": "x"},
        }
    ]
    t = build_transcript("cand-rv", turns)

    result = verify_transcript_hash(t)
    assert result["ok"], result["errors"]

    # tamper with hash
    tampered = dict(t, transcript_hash="bad" * 16)
    result2 = verify_transcript_hash(tampered)
    assert not result2["ok"]

    # compare identical transcripts
    cmp = compare_transcripts(t, t)
    assert cmp["ok"], cmp["errors"]
    print("PASS: transcript_replay_validator")


# ── Task 8: memory archive/search ────────────────────────────────────────────

def test_memory_archive_search():
    import transcript_memory_store as tms
    from transcript import build_transcript
    from deterministic_message_id import generate_message_id

    orig_dir = tms.MEMORY_DIR
    orig_index = tms.INDEX_FILE
    tmp = _tmp_dir()
    tms.MEMORY_DIR = tmp
    tms.INDEX_FILE = tmp / "index.json"

    try:
        mid = generate_message_id("cand-ms", "loop", "w", "user", 0)
        turns = [
            {
                "message_id": mid,
                "candidate_id": "cand-ms",
                "sender": "loop",
                "recipient": "w",
                "role": "user",
                "turn_number": 0,
                "payload": {"text": "archive test"},
            }
        ]
        t = build_transcript("cand-ms", turns)

        tid = tms.archive_transcript(t)
        assert tid == t["transcript_id"]

        found = tms.search_transcripts(candidate_id="cand-ms")
        assert len(found) == 1
        assert found[0]["transcript_id"] == tid

        loaded = tms.load_transcript(tid)
        assert loaded["transcript_hash"] == t["transcript_hash"]

        # archive again — no duplicate in index
        tms.archive_transcript(t)
        found2 = tms.search_transcripts(candidate_id="cand-ms")
        assert len(found2) == 1
        print("PASS: memory_archive_search")
    finally:
        tms.MEMORY_DIR = orig_dir
        tms.INDEX_FILE = orig_index
        shutil.rmtree(tmp, ignore_errors=True)


# ── Task 9: agent_loop multi_model_critique ───────────────────────────────────

def test_agent_loop_multi_model_critique():
    import message_bus as mb
    import transcript_memory_store as tms
    from agent_loop import run_multi_model_critique

    orig_inbox = mb.INBOX_DIR
    orig_outbox = mb.OUTBOX_DIR
    orig_mem = tms.MEMORY_DIR
    orig_idx = tms.INDEX_FILE
    tmp = _tmp_dir()
    mb.INBOX_DIR = tmp / "inbox"
    mb.OUTBOX_DIR = tmp / "outbox"
    tms.MEMORY_DIR = tmp / "mem"
    tms.INDEX_FILE = tmp / "mem" / "index.json"

    try:
        candidate = {
            "id": "cand-critique-001",
            "task_id": "multi_model_critique",
            "proposed_action": "test critique",
        }
        result = run_multi_model_critique(candidate)
        assert result["candidate_id"] == "cand-critique-001"
        assert result["transcript_id"].startswith("txn_")
        assert result["reply_count"] == 2
        assert result["arbitration"]["winner"] is not None
        print("PASS: agent_loop_multi_model_critique")
    finally:
        mb.INBOX_DIR = orig_inbox
        mb.OUTBOX_DIR = orig_outbox
        tms.MEMORY_DIR = orig_mem
        tms.INDEX_FILE = orig_idx
        shutil.rmtree(tmp, ignore_errors=True)


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_deterministic_message_id()
    test_worker_inbox_outbox()
    test_transcript_hash()
    test_transcript_replay_validator()
    test_memory_archive_search()
    test_agent_loop_multi_model_critique()
    print("ALL END-TO-END TESTS PASS")
