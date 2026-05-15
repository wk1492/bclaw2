"""
Deterministic transcript LLM-agent handoff primitive.

Fake model + two-agent exchange backed entirely by the transcript ledger.
No real model calls. No API keys. No randomness. No timestamps.
The ledger is the sole communication medium between agents.
"""
import hashlib
import json
from datetime import datetime, timezone

from transcript_event import make_transcript_event
from transcript_ledger import (
    append_transcript_event,
    replay_transcript_events,
    verify_mixed_ledger,
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fake_model(context: list) -> str:
    """
    Deterministic fake LLM. Output is derived solely from input content.
    No randomness, no timestamps, no API calls.
    Same input always produces same output; output changes when input changes.
    """
    if not context:
        return "horse faded late in race"
    contents = [msg.get("content", "") for msg in context]
    h = _sha256(_canonical(contents))[:12]
    last_content = context[-1].get("content", "")[:50]
    return f"possible pace overextension [{h}] re: {last_content}"


def run_agent_turn(
    agent_id: str,
    role: str,
    thread: list,
    ledger_path,
    *,
    run_id: str = "handoff_run_001",
    created_at: str = None,
    parent_message_id: str = None,
    references: list = None,
    model_fn=None,
    context_fn=None,
) -> dict:
    """
    Execute one agent turn: generate a response, wrap it as a validated
    transcript.message event, append to ledger. Returns the new event.

    model_fn   — callable(context: list) -> str. Default: fake_model.
                 Inject a live or deterministic function here. The ledger
                 boundary is preserved regardless: content goes through
                 make_transcript_event + append_transcript_event unchanged.
    context_fn — callable(thread: list) -> list. Transforms raw transcript
                 events before passing to model_fn. Default: identity.
    """
    ctx = context_fn(thread) if context_fn is not None else thread
    content = model_fn(ctx) if model_fn is not None else fake_model(ctx)
    if created_at is None:
        epoch = 1747000000 + int(_sha256(f"{agent_id}:{content}"), 16) % 86400
        created_at = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()

    event = make_transcript_event(
        run_id=run_id,
        sender=agent_id,
        recipient="broadcast",
        role=role,
        content=content,
        created_at=created_at,
        references=list(references) if references else [],
        parent_message_id=parent_message_id,
    )
    append_transcript_event(event, ledger_path)
    return event


def run_two_agent_handoff(ledger_path, *, model_fn=None, context_fn=None) -> dict:
    """
    Two-agent handoff: Agent A proposes from empty context; Agent B critiques
    using only Agent A's ledger-visible message. The ledger is the sole channel.

    model_fn / context_fn are forwarded to run_agent_turn unchanged.
    Omit both to use the deterministic fake_model (default for all tests).

    Returns:
        event_a, event_b, replay_order (list of message_ids), chain_ok (bool)
    """
    RUN_ID = "handoff_run_001"
    TS_A = "2026-05-11T10:00:00+00:00"
    TS_B = "2026-05-11T10:00:01+00:00"

    event_a = run_agent_turn(
        "agent_researcher", "proposal", [], ledger_path,
        run_id=RUN_ID, created_at=TS_A,
        model_fn=model_fn, context_fn=context_fn,
    )

    thread = replay_transcript_events(ledger_path)

    event_b = run_agent_turn(
        "agent_critic", "critique", thread, ledger_path,
        run_id=RUN_ID, created_at=TS_B,
        parent_message_id=event_a["message_id"],
        references=[event_a["message_id"]],
        model_fn=model_fn, context_fn=context_fn,
    )

    final_thread = replay_transcript_events(ledger_path)
    chain_status = verify_mixed_ledger(ledger_path)

    return {
        "event_a": event_a,
        "event_b": event_b,
        "replay_order": [e["message_id"] for e in final_thread],
        "chain_ok": chain_status.get("ok", False),
    }
