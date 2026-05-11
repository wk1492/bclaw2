import json
from pathlib import Path

from transcript_event import make_transcript_event, canonical_json
from transcript_ledger import (
    append_transcript_event,
    replay_transcript_events,
    verify_mixed_ledger,
)

RUN_ID = "run_agent_loop_001"
TS_A = "2026-05-10T12:00:00+00:00"
TS_B = "2026-05-10T12:00:01+00:00"
TS_C = "2026-05-10T12:00:02+00:00"


def run_transcript_agent_loop(path) -> dict:
    path = Path(path)

    proposal = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_a",
        recipient="agent_b",
        role="proposal",
        content="Add causal edge: fatigue -> error_rate",
        created_at=TS_A,
    )
    critique = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_b",
        recipient="agent_a",
        role="critique",
        content="Edge weight unsubstantiated; evidence threshold not met",
        created_at=TS_B,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    arbiter = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_arbiter",
        recipient="broadcast",
        role="arbiter",
        content="Proposal deferred pending evidence. Critique accepted.",
        created_at=TS_C,
        parent_message_id=critique["message_id"],
        references=[critique["message_id"], proposal["message_id"]],
    )

    transcript_events = [proposal, critique, arbiter]
    # Compute canonical output from transcript fields before ledger decoration adds timestamp
    canonical_output = canonical_json(transcript_events)

    for event in transcript_events:
        append_transcript_event(event, path)

    thread = replay_transcript_events(path)
    verification = verify_mixed_ledger(path)

    return {
        "run_id": RUN_ID,
        "event_count": len(thread),
        "roles": [e["role"] for e in thread],
        "replay_order": [e["message_id"] for e in thread],
        "parent_relationships": {
            e["message_id"]: e.get("parent_message_id") for e in thread
        },
        "hash_chain_ok": verification["ok"],
        "canonical_output": canonical_output,
    }
