import json
import sys

from agent_alerts import build_candidate_alerts, print_alerts
from ledger_writer import LedgerWriter
from orchestrator import run_pipeline
from worked_example import EXAMPLE_VALID

LEDGER_FILE = "idea_ledger.jsonl"


def main():
    candidates_file = sys.argv[1] if len(sys.argv) > 1 else "agent_candidates.json"
    candidates = json.load(open(candidates_file))
    _, summary = run_pipeline([EXAMPLE_VALID], return_summary=True, candidates=candidates)

    validations = summary["candidate_validation"]
    alerts = build_candidate_alerts(validations)

    writer = LedgerWriter(LEDGER_FILE)
    for item in validations:
        writer.append({"type": "candidate_validation", "result": item})
    for alert in alerts:
        writer.append({"type": "alert", "result": alert})

    print("WROTE_VALIDATIONS:", len(validations))
    print("ALERTS:", len(alerts))
    print_alerts(alerts)
    print("LEDGER_FILE:", LEDGER_FILE)


if __name__ == "__main__":
    main()
