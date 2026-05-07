from pathlib import Path
from underperformance_experiment import run_underperformance_experiment


def test_underperformance_experiment_does_not_write_ledger():
    ledger_path = Path("execution_ledger.jsonl")

    before_bytes = b""
    if ledger_path.exists():
        before_bytes = ledger_path.read_bytes()

    labeled, summary = run_underperformance_experiment(log_to_ledger=True)

    after_bytes = b""
    if ledger_path.exists():
        after_bytes = ledger_path.read_bytes()

    assert before_bytes == after_bytes, "underperformance_experiment wrote to ledger unexpectedly"
    assert summary.get("contract_id") == "underperformance_v1"


if __name__ == "__main__":
    test_underperformance_experiment_does_not_write_ledger()
    print("PASS: underperformance experiment does not write ledger")
