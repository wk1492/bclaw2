import json
import os
import tempfile

import pytest

from transcript_llm_agent import fake_model, run_agent_turn, run_two_agent_handoff
from transcript_ledger import replay_transcript_events, verify_mixed_ledger


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _msg(content):
    return {
        "event_type": "transcript.message",
        "message_id": "tmsg_aabbcc112233",
        "run_id": "run_test",
        "sender": "agent_a",
        "recipient": "broadcast",
        "role": "proposal",
        "content": content,
        "references": [],
        "parent_message_id": None,
        "created_at": "2026-05-11T10:00:00+00:00",
        "metadata": {},
    }


def _fresh_ledger():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.unlink(path)
    return path


# 1. fake_model is deterministic
def test_fake_model_deterministic():
    ctx = [_msg("horse faded late")]
    outputs = [fake_model(ctx) for _ in range(5)]
    assert len(set(outputs)) == 1
    empty_outputs = [fake_model([]) for _ in range(5)]
    assert len(set(empty_outputs)) == 1


# 2. fake_model output changes when input changes
def test_fake_model_changes_with_input():
    r1 = fake_model([_msg("horse faded late")])
    r2 = fake_model([_msg("different content entirely")])
    r3 = fake_model([])
    assert r1 != r2
    assert r1 != r3
    assert r2 != r3


# 3. run_agent_turn produces valid transcript.message event
def test_run_agent_turn_produces_valid_event():
    path = _fresh_ledger()
    event = run_agent_turn(
        "agent_x", "proposal", [], path,
        run_id="run_test", created_at="2026-05-11T10:00:00+00:00",
    )
    assert event["event_type"] == "transcript.message"
    assert event["sender"] == "agent_x"
    assert event["role"] == "proposal"
    assert event["message_id"].startswith("tmsg_")
    assert isinstance(event["content"], str) and len(event["content"]) > 0


# 4. run_agent_turn appends to ledger
def test_run_agent_turn_appends_to_ledger():
    path = _fresh_ledger()
    run_agent_turn(
        "agent_x", "proposal", [], path,
        run_id="run_test", created_at="2026-05-11T10:00:00+00:00",
    )
    events = replay_transcript_events(path)
    assert len(events) == 1
    assert events[0]["sender"] == "agent_x"
    assert events[0]["role"] == "proposal"


# 5. Agent B's context contains Agent A's message content
def test_agent_b_context_contains_agent_a_content():
    path = _fresh_ledger()
    result = run_two_agent_handoff(path)
    content_a = result["event_a"]["content"]
    content_b = result["event_b"]["content"]
    assert content_a[:40] in content_b, (
        f"Agent B response should reference Agent A's content.\n"
        f"  A: {content_a!r}\n  B: {content_b!r}"
    )


# 6. Two-agent handoff produces exactly two events
def test_two_agent_handoff_produces_two_events():
    path = _fresh_ledger()
    result = run_two_agent_handoff(path)
    assert len(result["replay_order"]) == 2
    events = replay_transcript_events(path)
    assert len(events) == 2
    senders = {e["sender"] for e in events}
    assert "agent_researcher" in senders
    assert "agent_critic" in senders


# 7. Replay order is parent-first (B references A)
def test_replay_order_parent_first():
    path = _fresh_ledger()
    result = run_two_agent_handoff(path)
    id_a = result["event_a"]["message_id"]
    id_b = result["event_b"]["message_id"]
    order = result["replay_order"]
    assert id_a in order and id_b in order
    assert order.index(id_a) < order.index(id_b), (
        f"A should appear before B in replay order: {order}"
    )


# 8. Repeated full runs are byte-identical
def test_repeated_full_runs_byte_identical():
    results = [_canonical(run_two_agent_handoff(_fresh_ledger())) for _ in range(3)]
    assert len(set(results)) == 1, "Repeated handoff runs produced different output"


# 9. Hash chain passes verification
def test_hash_chain_passes_verification():
    path = _fresh_ledger()
    result = run_two_agent_handoff(path)
    assert result["chain_ok"] is True
    chain = verify_mixed_ledger(path)
    assert chain.get("ok") is True
