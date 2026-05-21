import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


EXECUTION_LEDGER_FILE = Path("execution_ledger.jsonl")


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sha256_obj(obj):
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def hash_record_payload(record):
    payload = dict(record)
    payload.pop("hash", None)
    return sha256_obj(payload)


def build_run_record(run_type, input_data, output_data, metadata=None, timestamp=None):
    record = {
        "timestamp": timestamp or datetime.now(UTC).isoformat(),
        "type": run_type,
        "input": input_data,
        "output": output_data,
        "metadata": metadata or {},
    }
    record["hash"] = hash_record_payload(record)
    return record


def append_run(record):
    with EXECUTION_LEDGER_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    r = build_run_record(
        "candidate_validation",
        {"candidate_id": "001"},
        {"valid": True, "score": 95},
    )
    append_run(r)
    print("PASS: execution ledger wrote run")
    print(r["hash"])
