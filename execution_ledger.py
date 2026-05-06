import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


LEDGER_FILE = Path("execution_ledger.jsonl")


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sha256_obj(obj):
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def now():
    return datetime.now(UTC).isoformat()


def build_run_record(run_id, inputs, proposal, result, graph_before=None, graph_after=None):
    record = {
        "run_id": run_id,
        "timestamp": now(),
        "input_hash": sha256_obj(inputs),
        "proposal_hash": sha256_obj(proposal),
        "result_hash": sha256_obj(result),
        "graph_before_hash": sha256_obj(graph_before or {}),
        "graph_after_hash": sha256_obj(graph_after or {}),
        "inputs": inputs,
        "proposal": proposal,
        "result": result,
        "graph_before": graph_before or {},
        "graph_after": graph_after or {},
    }
    record["replay_hash"] = sha256_obj(record)
    return record


def append_run(record):
    with LEDGER_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


if __name__ == "__main__":
    demo = build_run_record(
        run_id="demo_run_001",
        inputs={"task": "demo"},
        proposal={"ready": True, "candidate_id": "demo"},
        result={"executed": True, "status": "simulated_execution"},
    )
    append_run(demo)
    print("PASS: execution ledger wrote run")
    print(demo["replay_hash"])
