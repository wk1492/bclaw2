import json
from pathlib import Path

from checkpoint_manager import CheckpointManager


LEDGER_FILE = Path("execution_ledger.jsonl")


def load_execution_records(path=LEDGER_FILE):
    if not path.exists():
        return []

    records = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def replay_summary(records):
    return {
        "record_count": len(records),
        "types": count_types(records),
        "hashes": [r.get("hash") for r in records if r.get("hash")],
    }


def count_types(records):
    counts = {}
    for r in records:
        t = r.get("type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts


def replay_latest_checkpoint():
    mgr = CheckpointManager()
    latest = mgr.latest_checkpoint()

    if latest is None:
        return {
            "checkpoint_found": False,
            "path": None,
        }

    data = mgr.load_checkpoint(latest)

    return {
        "checkpoint_found": True,
        "path": str(latest),
        "checkpoint_type": data.get("checkpoint_type"),
        "hash": data.get("hash"),
        "state": data.get("state"),
    }


if __name__ == "__main__":
    records = load_execution_records()
    print(json.dumps({
        "execution_replay": replay_summary(records),
        "latest_checkpoint": replay_latest_checkpoint(),
    }, indent=2, sort_keys=True))
