import json
from pathlib import Path
from datetime import UTC, datetime

from candidate_validator import validate_candidate, score_candidate
from failure_synthesizer import synthesize
from generate_candidates import generate_new_candidates
from execution_planner import plan_execution
from execution_proposal import propose_execution
from ledger_writer import LedgerWriter

STATE_FILE = Path("agent_state.json")
LEDGER_FILE = Path("idea_ledger.jsonl")
CANDIDATES_FILE = Path("agent_candidates.json")
ledger_writer = LedgerWriter()

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

    # ✅ ADD: planning + proposal
    plan = plan_execution(candidates)
    proposal = propose_execution(plan)

    ledger_writer.append({
        "timestamp": now(),
        "type": "candidate_validation",
        "results": results,
        "plan": {
            "ready_count": len(plan.get("ready", [])),
            "blocked_count": len(plan.get("blocked", [])),
        },
        "proposal": proposal,
    })

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
