import json
from pathlib import Path

from ledger_writer import LedgerWriter, verify_ledger


def test_ledger_writer_roundtrip():
    path = Path("tmp_test_execution_ledger.jsonl")
    path.unlink(missing_ok=True)

    writer = LedgerWriter(path)
    writer.append({"type": "a", "payload": {"x": 1}})
    writer.append({"type": "b", "payload": {"y": 2}})

    result = verify_ledger(path)
    assert result["ok"] is True
    assert result["count"] == 2

    path.unlink(missing_ok=True)


def test_ledger_detects_tamper():
    path = Path("tmp_test_tamper_ledger.jsonl")
    path.unlink(missing_ok=True)

    writer = LedgerWriter(path)
    writer.append({"type": "a", "payload": {"x": 1}})

    event = json.loads(path.read_text().splitlines()[0])
    event["payload"]["x"] = 999
    path.write_text(json.dumps(event) + "\n")

    result = verify_ledger(path)
    assert result["ok"] is False
    assert result["failures"]

    path.unlink(missing_ok=True)


if __name__ == "__main__":
    test_ledger_writer_roundtrip()
    test_ledger_detects_tamper()
    print("PASS: ledger writer tests")
