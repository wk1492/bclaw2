import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from state_serializer import canonical_json, state_hash


GENESIS_HASH = "0" * 64


def utc_now():
    return datetime.now(UTC).isoformat()


def event_hash(event):
    clean = {
        k: v for k, v in event.items()
        if k not in {"event_hash", "rolling_hash"}
    }
    return hashlib.sha256(canonical_json(clean).encode("utf-8")).hexdigest()


class LedgerWriter:
    def __init__(self, path="execution_ledger.jsonl"):
        self.path = Path(path)
        self.current_rolling_hash = self._load_last_hash()

    def _load_last_hash(self):
        if not self.path.exists():
            return GENESIS_HASH

        last = None
        for line in self.path.read_text().splitlines():
            if line.strip():
                last = json.loads(line)

        return last.get("rolling_hash", GENESIS_HASH) if last else GENESIS_HASH

    def append(self, event):
        event = dict(event)
        event.setdefault("timestamp", utc_now())

        clean_for_id = {
            k: v for k, v in event.items()
            if k not in {"event_id", "event_hash", "rolling_hash"}
        }

        event["previous_hash"] = self.current_rolling_hash
        event["event_hash"] = hashlib.sha256(canonical_json(clean_for_id).encode("utf-8")).hexdigest()
        event["event_id"] = "evt_" + event["event_hash"][:16]
        event["rolling_hash"] = hashlib.sha256(
            (self.current_rolling_hash + event["event_hash"]).encode("utf-8")
        ).hexdigest()

        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")

        self.current_rolling_hash = event["rolling_hash"]
        return event


def verify_ledger(path="execution_ledger.jsonl"):
    path = Path(path)
    if not path.exists():
        return {"ok": True, "count": 0, "failures": []}

    current = GENESIS_HASH
    failures = []
    count = 0

    for count, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            failures.append(f"event {count}: invalid JSON (truncated or corrupt line)")
            break

        expected_previous = current
        if event.get("previous_hash") != expected_previous:
            failures.append(f"event {count}: previous_hash mismatch")
            break

        clean_for_id = {
            k: v for k, v in event.items()
            if k not in {"event_id", "event_hash", "rolling_hash", "previous_hash"}
        }

        recomputed_event_hash = hashlib.sha256(
            canonical_json(clean_for_id).encode("utf-8")
        ).hexdigest()

        if event.get("event_hash") != recomputed_event_hash:
            failures.append(f"event {count}: event_hash mismatch")
            break

        recomputed_rolling = hashlib.sha256(
            (current + recomputed_event_hash).encode("utf-8")
        ).hexdigest()

        if event.get("rolling_hash") != recomputed_rolling:
            failures.append(f"event {count}: rolling_hash mismatch")
            break

        if event.get("state") is not None and event.get("state_hash") is not None:
            if state_hash(event["state"]) != event["state_hash"]:
                failures.append(f"event {count}: state_hash mismatch")
                break

        current = event["rolling_hash"]

    return {
        "ok": len(failures) == 0,
        "count": count,
        "failures": failures,
        "last_rolling_hash": current,
    }


if __name__ == "__main__":
    writer = LedgerWriter("execution_ledger_demo.jsonl")
    event = writer.append({
        "type": "demo_event",
        "payload": {"x": 1, "y": 2},
    })
    print(json.dumps(event, indent=2, sort_keys=True))
    print(json.dumps(verify_ledger("execution_ledger_demo.jsonl"), indent=2, sort_keys=True))
