import json
from pathlib import Path

from candidate_validator import validate_candidate
from failure_synthesizer import synthesize

STATE_FILE = Path("agent_state.json")
LEDGER_FILE = Path("idea_ledger.jsonl")
CANDIDATES_FILE = Path("agent_candidates.json")


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"run_count": 0, "last_status": "new"}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


def append_ledger(record):
    with LEDGER_FILE.open("a") as f:
        f.write(json.dumps(record) + "\n")


def main():
    state = load_state()
    state["run_count"] += 1

    if not CANDIDATES_FILE.exists():
        print("ALERT: no candidates file")
        state["last_status"] = "no_candidates"
        save_state(state)
        return

    candidates = json.loads(CANDIDATES_FILE.read_text())

    results = []
    for c in candidates:
        try:
            validate_candidate(c)
            results.append({"id": c["id"], "valid": True})
        except Exception as e:
            results.append({"id": c.get("id","unknown"), "valid": False, "error": str(e)})

    append_ledger({"results": results})

    failures = [r for r in results if not r["valid"]]
    if failures:
        proposals = synthesize(json.dumps(failures))
        print("ALERT: failures detected")
        print(proposals)
        state["last_status"] = "failures"
    else:
        print("PASS: all candidates valid")
        state["last_status"] = "ok"

    save_state(state)


if __name__ == "__main__":
    main()
