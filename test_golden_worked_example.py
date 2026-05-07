import hashlib
import json
import subprocess
import sys
from pathlib import Path

from underperformance_experiment import run_underperformance_experiment, TOY_RACES

GOLDEN = Path("worked_examples/golden/underperformance_happy_path.json")
LEDGER = Path("execution_ledger.jsonl")


def _canonical(obj):
    return json.dumps(obj, indent=2, sort_keys=True)


def _ledger_hash():
    return hashlib.sha256(LEDGER.read_bytes()).hexdigest() if LEDGER.exists() else ""


def test_golden_output():
    labeled, summary = run_underperformance_experiment(log_to_ledger=False)
    computed = {
        "contract_id": summary["contract_id"],
        "input_races": TOY_RACES,
        "labeled": labeled,
        "summary": summary,
    }
    computed_str = _canonical(computed)
    golden_str = GOLDEN.read_text()
    assert computed_str == golden_str, (
        f"golden mismatch\n--- golden ---\n{golden_str}\n--- computed ---\n{computed_str}"
    )


def test_ledger_not_mutated():
    before = _ledger_hash()
    run_underperformance_experiment(log_to_ledger=False)
    after = _ledger_hash()
    assert before == after, "execution_ledger.jsonl was mutated by golden-output generation"


def test_replay_verify():
    result = subprocess.run(
        [sys.executable, "replay_runner.py", "--verify"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def main():
    test_golden_output()
    print("PASS: golden output matches")

    test_ledger_not_mutated()
    print("PASS: ledger not mutated")

    test_replay_verify()
    print("PASS: replay_runner --verify")

    print(json.dumps({"status": "ok", "golden": str(GOLDEN)}, indent=2))


if __name__ == "__main__":
    main()
