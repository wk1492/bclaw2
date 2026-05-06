import argparse
import json
from pathlib import Path

from checkpoint_manager import CheckpointManager
from ledger_writer import verify_ledger
from state_serializer import state_hash


LEDGER_FILE = Path("execution_ledger.jsonl")


def load_execution_records(path=LEDGER_FILE):
    if not path.exists():
        return []

    records = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def count_types(records):
    counts = {}
    for r in records:
        t = r.get("type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts


def replay_summary(records):
    return {
        "record_count": len(records),
        "types": count_types(records),
        "hashes": [r.get("hash") or r.get("event_hash") for r in records if r.get("hash") or r.get("event_hash")],
    }


def replay_latest_checkpoint():
    mgr = CheckpointManager()
    latest = mgr.latest_checkpoint()

    if latest is None:
        return {"checkpoint_found": False, "path": None}

    data = mgr.load_checkpoint(latest)

    return {
        "checkpoint_found": True,
        "path": str(latest),
        "checkpoint_id": data.get("checkpoint_id"),
        "checkpoint_type": data.get("checkpoint_type"),
        "state_hash": data.get("state_hash"),
        "verified_state_hash": state_hash(data.get("state")),
    }


def verify_all():
    print("=== BCLAW2 Full Deterministic Verification ===")

    ledger_result = verify_ledger(LEDGER_FILE)
    print(json.dumps({"ledger": ledger_result}, indent=2, sort_keys=True))

    checkpoint_result = replay_latest_checkpoint()
    print(json.dumps({"latest_checkpoint": checkpoint_result}, indent=2, sort_keys=True))

    ok = ledger_result["ok"]

    if checkpoint_result.get("checkpoint_found"):
        ok = ok and checkpoint_result.get("state_hash") == checkpoint_result.get("verified_state_hash")

    print(f"VERIFICATION: {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.verify:
        raise SystemExit(0 if verify_all() else 1)

    records = load_execution_records()
    print(json.dumps({
        "execution_replay": replay_summary(records),
        "latest_checkpoint": replay_latest_checkpoint(),
    }, indent=2, sort_keys=True))
