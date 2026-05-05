import json
import sys
from datetime import UTC, datetime

from agent_alerts import build_candidate_alerts, print_alerts
from orchestrator import run_pipeline
from worked_example import EXAMPLE_VALID

LEDGER_FILE = "idea_ledger.jsonl"


def main():
    candidates_file = sys.argv[1] if len(sys.argv) > 1 else "agent_candidates.json"
    candidates = json.load(open(candidates_file))
    _, summary = run_pipeline([EXAMPLE_VALID], return_summary=True, candidates=candidates)

    validations = summary["candidate_validation"]
    alerts = build_candidate_alerts(validations)

    with open(LEDGER_FILE, "a") as f:
        for item in validations:
            record = {
                "timestamp": datetime.now(UTC).isoformat(),
                "type": "candidate_validation",
                "result": item,
            }
            f.write(json.dumps(record) + "\n")
        for alert in alerts:
            record = {
                "timestamp": datetime.now(UTC).isoformat(),
                "type": "alert",
                "result": alert,
            }
            f.write(json.dumps(record) + "\n")

    print("WROTE_VALIDATIONS:", len(validations))
    print("ALERTS:", len(alerts))
    print_alerts(alerts)
    print("LEDGER_FILE:", LEDGER_FILE)


if __name__ == "__main__":
    main()
