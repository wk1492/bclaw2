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

RUN_ID = "bclaw4_comm_compute_001"
_TS_PROPOSAL = "2026-05-15T12:00:00+00:00"
_TS_CRITIQUE = "2026-05-15T12:00:01+00:00"
_TS_ARBITER  = "2026-05-15T12:00:02+00:00"
_TS_RESULT   = "2026-05-15T12:00:03+00:00"


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_transcript_score(events: list) -> dict:
    """
    Pure, order-independent score derived from a transcript event list.
    Does not read the ledger or call any I/O.
    """
    message_count = len(events)
    critiques = [e for e in events if e.get("role") == "critique"]
    critique_count = len(critiques)
    arbiters = [e for e in events if e.get("role") == "arbiter"]

    arbiter_refs: set = set()
    for arb in arbiters:
        arbiter_refs.update(arb.get("references", []))

    critique_ids = {c["message_id"] for c in critiques}
    unresolved_count = len(critique_ids - arbiter_refs)
    arbitration_status = "complete" if arbiters else "pending"

    return {
        "message_count": message_count,
        "critique_count": critique_count,
        "unresolved_count": unresolved_count,
        "arbitration_status": arbitration_status,
    }


def run_comm_compute_loop(ledger_path=None) -> dict:
    """
    Phase 1: emit proposal → critique → arbiter.
    Phase 2: replay, compute score, append as system event.
    Phase 3: verify chain, build deterministic summary.
    """
    if ledger_path is None:
        fd, ledger_path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        Path(ledger_path).unlink(missing_ok=True)

    # Phase 1 — communication
    proposal = make_transcript_event(
        run_id=RUN_ID,
        sender="bclaw4_agent_a",
        recipient="broadcast",
        role="proposal",
        content="Proposal: assert causal edge workload->error_rate with weight=0.6",
        created_at=_TS_PROPOSAL,
    )
    critique = make_transcript_event(
        run_id=RUN_ID,
        sender="bclaw4_agent_b",
        recipient="bclaw4_agent_a",
        role="critique",
        content="Critique: weight=0.6 lacks longitudinal support; suggest weight<=0.4",
        created_at=_TS_CRITIQUE,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    arbiter = make_transcript_event(
        run_id=RUN_ID,
        sender="bclaw4_arbiter",
        recipient="broadcast",
        role="arbiter",
        content="Arbiter: critique accepted; edge deferred pending longitudinal evidence",
        created_at=_TS_ARBITER,
        parent_message_id=critique["message_id"],
        references=[critique["message_id"], proposal["message_id"]],
    )
    for event in (proposal, critique, arbiter):
        append_transcript_event(event, ledger_path)

    # Phase 2 — computation
    comm_events = replay_transcript_events(ledger_path)
    score = compute_transcript_score(comm_events)

    result_event = make_transcript_event(
        run_id=RUN_ID,
        sender="bclaw4_compute",
        recipient="broadcast",
        role="system",
        content=_canonical(score),
        created_at=_TS_RESULT,
        parent_message_id=arbiter["message_id"],
        references=[proposal["message_id"], critique["message_id"], arbiter["message_id"]],
    )
    append_transcript_event(result_event, ledger_path)

    # Phase 3 — verification
    all_events = replay_transcript_events(ledger_path)
    chain = verify_mixed_ledger(ledger_path)

    summary_body = {
        "run_id": RUN_ID,
        "event_count": len(all_events),
        "score": score,
        "result_message_id": result_event["message_id"],
    }
    summary_id = "ccl_" + _sha256(_canonical(summary_body))[:24]

    return {
        "summary_id": summary_id,
        "run_id": RUN_ID,
        "ledger_path": str(ledger_path),
        "communication": {
            "proposal_id": proposal["message_id"],
            "critique_id": critique["message_id"],
            "arbiter_id": arbiter["message_id"],
        },
        "computation": score,
        "result_message_id": result_event["message_id"],
        "chain_ok": chain.get("ok", False),
        "event_count": len(all_events),
    }
