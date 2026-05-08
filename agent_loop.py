import json
from datetime import UTC, datetime
from pathlib import Path

from candidate_validator import validate_candidate, score_candidate
from deterministic_message_id import generate_message_id
from execution_planner import plan_execution
from execution_proposal import propose_execution
from failure_synthesizer import synthesize
from generate_candidates import generate_new_candidates
from ledger_event_status import classify_candidate_results
from ledger_writer import LedgerWriter
from message_bus import clear_inbox, clear_outbox, put_inbox
from transcript import build_transcript
from transcript_memory_store import archive_transcript
from worker_runtime_manager import collect_outbox_replies, run_workers_once

STATE_FILE = Path("agent_state.json")
LEDGER_FILE = Path("idea_ledger.jsonl")
CANDIDATES_FILE = Path("agent_candidates.json")
ledger_writer = LedgerWriter()

CRITIQUE_WORKERS = [
    {"worker_id": "dia_worker_a", "model_name": "stub", "backend": "stub"},
    {"worker_id": "dia_worker_b", "model_name": "stub", "backend": "stub"},
]


def now():
    return datetime.now(UTC).isoformat()

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"run_count": 0, "last_status": "new", "last_task": None}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


def load_or_generate_candidates():
    if not CANDIDATES_FILE.exists() or CANDIDATES_FILE.stat().st_size < 20:
        print("INFO: generating candidates because file is missing or empty")
        candidates = generate_new_candidates()
        CANDIDATES_FILE.write_text(json.dumps(candidates, indent=2) + "\n")
        return candidates

    candidates = json.loads(CANDIDATES_FILE.read_text())
    active = [c for c in candidates if c.get("status") not in {"implemented", "archived"}]
    if not active:
        print("INFO: generating candidates because active queue is exhausted")
        candidates = generate_new_candidates()
        CANDIDATES_FILE.write_text(json.dumps(candidates, indent=2) + "\n")
        return candidates

    return candidates

def _arbitrate(replies: list) -> dict:
    """Deterministic arbitration: select reply with lexicographically lowest message_id."""
    if not replies:
        return {"winner": None, "reason": "no_replies"}
    winner = min(replies, key=lambda r: r["message_id"])
    return {"winner": winner, "reason": "lowest_message_id"}


def run_multi_model_critique(candidate: dict) -> dict:
    """
    Drive a multi-model critique for a single candidate.
    Creates inbox messages, runs workers once, collects outbox replies,
    builds transcript, arbitrates deterministically.
    Returns a result dict suitable for a single ledger event.
    Does NOT write the ledger — caller (main) does that.
    """
    candidate_id = candidate.get("id") or candidate.get("candidate_id", "unknown")
    worker_ids = [w["worker_id"] for w in CRITIQUE_WORKERS]

    # Clear stale inbox/outbox for this run
    for wid in worker_ids:
        clear_inbox(wid)
        clear_outbox(wid)

    # Create one inbox message per worker
    for wid in worker_ids:
        msg_id = generate_message_id(
            candidate_id=candidate_id,
            sender="agent_loop",
            recipient=wid,
            role="user",
            turn_number=0,
        )
        put_inbox({
            "message_id": msg_id,
            "candidate_id": candidate_id,
            "sender": "agent_loop",
            "recipient": wid,
            "role": "user",
            "turn_number": 0,
            "payload": {
                "text": f"Critique this candidate: {json.dumps(candidate)}",
            },
        })

    run_workers_once(CRITIQUE_WORKERS)

    replies = collect_outbox_replies(worker_ids)

    turns = []
    for wid in worker_ids:
        msg_id = generate_message_id(
            candidate_id=candidate_id,
            sender="agent_loop",
            recipient=wid,
            role="user",
            turn_number=0,
        )
        turns.append({
            "message_id": msg_id,
            "candidate_id": candidate_id,
            "sender": "agent_loop",
            "recipient": wid,
            "role": "user",
            "turn_number": 0,
            "payload": {"text": f"Critique this candidate: {json.dumps(candidate)}"},
        })
    turns.extend(replies)

    transcript = build_transcript(candidate_id, turns)
    archive_transcript(transcript)

    arbitration = _arbitrate(replies)

    return {
        "candidate_id": candidate_id,
        "transcript_id": transcript["transcript_id"],
        "transcript_hash": transcript["transcript_hash"],
        "reply_count": len(replies),
        "arbitration": arbitration,
    }


def main():
    state = load_state()
    state["run_count"] += 1
    state["last_task"] = "persistent_agent_loop"

    candidates = load_or_generate_candidates()

    results = []
    for c in candidates:
        try:
            validate_candidate(c)
            results.append({"id": c.get("id"), "valid": True, "score": score_candidate(c)})
        except Exception as e:
            results.append({"id": c.get("id", "unknown"), "valid": False, "error": str(e)})

    plan = plan_execution(candidates)
    proposal = propose_execution(plan)

    event_status = classify_candidate_results(results)

    ledger_writer.append({
        "timestamp": now(),
        "type": "candidate_validation",
        "event_status": event_status,
        "results": results,
        "plan": {
            "ready_count": len(plan.get("ready", [])),
            "blocked_count": len(plan.get("blocked", [])),
        },
        "proposal": proposal,
    })

    # multi_model_critique path
    critique_candidates = [c for c in candidates if c.get("task_id") == "multi_model_critique"]
    for c in critique_candidates:
        critique_result = run_multi_model_critique(c)
        ledger_writer.append({
            "timestamp": now(),
            "type": "multi_model_critique",
            "critique": critique_result,
        })
        print(f"CRITIQUE: {critique_result['candidate_id']} transcript={critique_result['transcript_id']}")

    failures = [r for r in results if not r.get("valid")]
    if failures:
        proposals = synthesize(json.dumps(failures))
        state["last_status"] = "failures"
        print("ALERT: validation failures detected")
        print(json.dumps(proposals, indent=2))
    else:
        state["last_status"] = "ok"
        print("PASS: all candidates valid")

    state["last_proposal"] = proposal
    save_state(state)

    print(f"PROPOSAL: {proposal}")
    print(f"STATE: {state['last_status']} | Run #{state['run_count']}")

if __name__ == "__main__":
    main()
