import json
import subprocess
import sys
from pathlib import Path

from ledger_writer import verify_ledger
from serializer_registry import canonical_serialize


def run(cmd):
    print(f"=== RUN: {' '.join(cmd)} ===")
    result = subprocess.run(cmd, text=True, capture_output=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def assert_serializer():
    a = {"b": 2, "a": 1, "items": {"z", "x", "y"}}
    b = {"items": {"y", "z", "x"}, "a": 1, "b": 2}
    assert canonical_serialize(a) == canonical_serialize(b)


def assert_checkpoint():
    cp = Path("checkpoints/cp_test_envelope.json")
    assert cp.exists(), "checkpoint missing"
    data = json.loads(cp.read_text())
    assert "state_hash" in data, "checkpoint missing state_hash"


def main():
    print("=== BCLAW2 SYSTEM VERIFICATION ===")

    assert_serializer()
    print("PASS: serializer deterministic")

    run([sys.executable, "agent_loop.py"])

    ledger = verify_ledger("execution_ledger.jsonl")
    assert ledger["ok"] is True
    assert ledger["count"] >= 1
    print("PASS: ledger verified")

    assert_checkpoint()
    print("PASS: checkpoint present")

    run([sys.executable, "replay_runner.py", "--verify"])

    print("=== SYSTEM VERIFICATION: PASS ===")


if __name__ == "__main__":
    main()
