import json
import sys

from orchestrator import run_pipeline
from worked_example import EXAMPLE_VALID

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 run_agent_candidates.py agent_candidates.json")

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        candidates = json.load(f)

    _, summary = run_pipeline(
        [EXAMPLE_VALID],
        return_summary=True,
        candidates=candidates,
    )

    print(json.dumps(summary["candidate_validation"], indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
