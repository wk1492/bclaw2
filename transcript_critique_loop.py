import json
import tempfile
from pathlib import Path

from transcript_event import make_transcript_event, canonical_json
from transcript_ledger import (
    append_transcript_event,
    replay_transcript_events,
    verify_mixed_ledger,
)

RUN_ID = "run_critique_loop_001"
TS_A = "2026-05-10T13:00:00+00:00"
TS_B = "2026-05-10T13:00:01+00:00"
TS_C = "2026-05-10T13:00:02+00:00"
TS_D = "2026-05-10T13:00:03+00:00"


def run_transcript_critique_loop(path) -> dict:
    path = Path(path)

    proposal = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_proposer",
        recipient="broadcast",
        role="proposal",
        content="Add causal edge: workload -> burnout",
        created_at=TS_A,
    )
    critique_a = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_critic_a",
        recipient="agent_proposer",
        role="critique",
        content="Workload -> burnout lacks longitudinal support",
        created_at=TS_B,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    critique_b = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_critic_b",
        recipient="agent_proposer",
        role="critique",
        content="Alternative pathway: workload -> stress -> burnout is more defensible",
        created_at=TS_C,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    arbiter = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_arbiter",
        recipient="broadcast",
        role="arbiter",
        content="Proposal deferred. Both critiques accepted. Indirect pathway preferred.",
        created_at=TS_D,
        parent_message_id=critique_a["message_id"],
        references=[
            critique_a["message_id"],
            critique_b["message_id"],
            proposal["message_id"],
        ],
    )

    transcript_events = [proposal, critique_a, critique_b, arbiter]
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
        "topology": {
            "proposal": proposal["message_id"],
            "critiques": [critique_a["message_id"], critique_b["message_id"]],
            "arbiter": arbiter["message_id"],
            "arbiter_references": arbiter["references"],
        },
        "hash_chain_ok": verification["ok"],
        "canonical_output": canonical_output,
    }


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "critique_loop.jsonl"
        summary = run_transcript_critique_loop(path)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
