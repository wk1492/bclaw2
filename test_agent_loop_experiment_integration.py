import json
from pathlib import Path

from ledger_writer import verify_ledger

LEDGER = Path("execution_ledger.jsonl")


def test_agent_loop_generates_valid_experiment_candidate():
    data = json.loads(Path("agent_candidates.json").read_text())

    assert len(data) >= 1

    c = data[0]

    assert c["task_id"] == "underperformance_v1"
    assert c["status"] == "proposed"
    assert c["candidate_id"]
    assert c["action"]


def test_ledger_is_still_valid_after_agent_loop_runs():
    result = verify_ledger()

    assert result["ok"] is True
    assert result["failures"] == []


if __name__ == "__main__":
    test_agent_loop_generates_valid_experiment_candidate()
    test_ledger_is_still_valid_after_agent_loop_runs()
    print("PASS: agent loop experiment integration")
