import hashlib
import json
import os
import tempfile
from pathlib import Path

from transcript_event import make_transcript_event
from transcript_ledger import (
    append_transcript_event,
    replay_transcript_events,
    verify_mixed_ledger,
)
from transcript_topology import linearize_transcript_topology

STATE_VERSION = 1
SNAPSHOT_MARKER = "transcript.state_snapshot"
RUN_ID = "bclaw4_state_engine_001"

_TS = {
    "proposal":   "2026-05-15T13:00:00+00:00",
    "critique_a": "2026-05-15T13:00:01+00:00",
    "critique_b": "2026-05-15T13:00:02+00:00",
    "arbiter":    "2026-05-15T13:00:03+00:00",
    "snapshot":   "2026-05-15T13:00:04+00:00",
}


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def reduce_transcript_state(events: list) -> dict:
    """
    Pure, order-independent reducer. Deduplicates by message_id (first wins).
    Ignores role='system' snapshot events.
    """
    seen: set = set()
    unique: list = []
    for e in events:
        mid = e.get("message_id")
        if mid and mid not in seen:
            seen.add(mid)
            unique.append(e)

    comm = [e for e in unique if e.get("role") in ("proposal", "critique", "arbiter", "reply")]

    proposals = [e for e in comm if e.get("role") == "proposal"]
    critiques  = [e for e in comm if e.get("role") == "critique"]
    arbiters   = [e for e in comm if e.get("role") == "arbiter"]

    arbiter_refs: set = set()
    for arb in arbiters:
        arbiter_refs.update(arb.get("references", []))

    critique_ids = {c["message_id"] for c in critiques}
    accepted_count   = len(critique_ids & arbiter_refs)
    unresolved_count = len(critique_ids - arbiter_refs)

    rejected: set = set()
    for p in proposals:
        p_id = p["message_id"]
        for c in critiques:
            if c.get("parent_message_id") == p_id or p_id in c.get("references", []):
                if c["message_id"] in arbiter_refs:
                    rejected.add(p_id)
                    break
    rejected_count = len(rejected)

    participants = sorted({e.get("sender", "") for e in comm if e.get("sender")})
    last_status  = linearize_transcript_topology(comm)[-1]["role"] if comm else "none"
    thread_ids   = sorted(e["message_id"] for e in comm)
    transcript_hash = _sha256(_canonical(thread_ids))

    return {
        "proposal_count":   len(proposals),
        "critique_count":   len(critiques),
        "accepted_count":   accepted_count,
        "rejected_count":   rejected_count,
        "unresolved_count": unresolved_count,
        "participants":     participants,
        "last_status":      last_status,
        "thread_ids":       thread_ids,
        "transcript_hash":  transcript_hash,
    }


def run_state_engine(ledger_path=None) -> dict:
    """
    Phase 1: emit proposal + 2 critiques + arbiter.
    Phase 2: reduce to canonical state, append snapshot.
    Phase 3: verify chain.
    """
    if ledger_path is None:
        fd, ledger_path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        Path(ledger_path).unlink(missing_ok=True)

    proposal = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_a",
        recipient="broadcast",
        role="proposal",
        content="Proposal: assert causal edge fatigue->error_rate with weight=0.6",
        created_at=_TS["proposal"],
    )
    critique_a = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_b",
        recipient="agent_a",
        role="critique",
        content="Challenge: weight=0.6 overstated; longitudinal data absent",
        created_at=_TS["critique_a"],
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    critique_b = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_c",
        recipient="agent_a",
        role="critique",
        content="Challenge: confounder workload_history not controlled",
        created_at=_TS["critique_b"],
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    arbiter = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_arbiter",
        recipient="broadcast",
        role="arbiter",
        content="Arbiter: both critiques accepted; proposal deferred pending controls",
        created_at=_TS["arbiter"],
        parent_message_id=critique_a["message_id"],
        references=[critique_a["message_id"], critique_b["message_id"], proposal["message_id"]],
    )
    for ev in (proposal, critique_a, critique_b, arbiter):
        append_transcript_event(ev, ledger_path)

    comm_events = replay_transcript_events(ledger_path)
    state = reduce_transcript_state(comm_events)

    snapshot_content = _canonical({
        "marker": SNAPSHOT_MARKER,
        "state_version": STATE_VERSION,
        "derived_state": state,
    })
    snapshot_event = make_transcript_event(
        run_id=RUN_ID,
        sender="bclaw4_state_engine",
        recipient="broadcast",
        role="system",
        content=snapshot_content,
        created_at=_TS["snapshot"],
        references=[
            proposal["message_id"], critique_a["message_id"],
            critique_b["message_id"], arbiter["message_id"],
        ],
    )
    append_transcript_event(snapshot_event, ledger_path)

    all_events = replay_transcript_events(ledger_path)
    chain = verify_mixed_ledger(ledger_path)

    summary_body = {
        "run_id": RUN_ID,
        "state_version": STATE_VERSION,
        "derived_state": state,
        "snapshot_message_id": snapshot_event["message_id"],
    }
    summary_id = "ste_" + _sha256(_canonical(summary_body))[:24]

    return {
        "summary_id": summary_id,
        "run_id": RUN_ID,
        "ledger_path": str(ledger_path),
        "derived_state": state,
        "snapshot_message_id": snapshot_event["message_id"],
        "chain_ok": chain.get("ok", False),
        "event_count": len(all_events),
    }
