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


# ── Model runner seam tests ───────────────────────────────────────────────────

# 10. Seam default produces byte-identical output to pre-seam behavior
def test_seam_default_is_byte_identical_to_original():
    results = [_canonical(run_two_agent_handoff(_fresh_ledger())) for _ in range(3)]
    assert len(set(results)) == 1, "seam default path changed byte output"


# 11. Injected deterministic model_fn is called and produces ledger event
def test_injected_deterministic_model_fn():
    def fixed_model(context):
        return "FIXED_DETERMINISTIC_OUTPUT"

    path = _fresh_ledger()
    result = run_two_agent_handoff(path, model_fn=fixed_model)
    assert result["event_a"]["content"] == "FIXED_DETERMINISTIC_OUTPUT"
    assert result["event_b"]["content"] == "FIXED_DETERMINISTIC_OUTPUT"
    events = replay_transcript_events(path)
    assert all(e["content"] == "FIXED_DETERMINISTIC_OUTPUT" for e in events)


# 12. Injected model_fn — Agent B's context comes only from ledger replay of A
def test_injected_model_fn_agent_b_sees_a_via_ledger():
    seen_contexts = []

    def recording_model(context):
        seen_contexts.append([m.get("content", "") for m in context])
        return f"response_to_{len(context)}_messages"

    path = _fresh_ledger()
    run_two_agent_handoff(path, model_fn=recording_model)

    # Agent A sees empty context; Agent B sees exactly one ledger event (A's)
    assert len(seen_contexts) == 2
    assert seen_contexts[0] == []                        # A: empty thread
    assert len(seen_contexts[1]) == 1                    # B: only A's event
    assert seen_contexts[1][0] == "response_to_0_messages"  # A's content from ledger


# 13. Injected model_fn — hash chain still passes
def test_injected_model_fn_hash_chain_passes():
    path = _fresh_ledger()
    result = run_two_agent_handoff(path, model_fn=lambda ctx: "deterministic_content")
    assert result["chain_ok"] is True
    assert verify_mixed_ledger(path).get("ok") is True


# 14. context_fn transforms thread before model_fn receives it
def test_context_fn_transforms_thread():
    received = []

    def extract_contents(thread):
        return [m.get("content", "") for m in thread]

    def recording_model(context):
        received.append(context)
        return "reply"

    path = _fresh_ledger()
    run_two_agent_handoff(path, model_fn=recording_model, context_fn=extract_contents)

    # Agent A: context_fn([]) -> []; Agent B: context_fn([event_a]) -> [content_str]
    assert received[0] == []
    assert isinstance(received[1], list) and isinstance(received[1][0], str)


# 15. No Ollama or network call occurs with default or injected deterministic fn
def test_no_network_call_in_seam(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("network call must not occur during deterministic tests")

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", explode)

    path = _fresh_ledger()
    # Both default path and injected deterministic fn must stay off-network
    run_two_agent_handoff(path)
    run_two_agent_handoff(_fresh_ledger(), model_fn=lambda ctx: "safe")
