from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

UTC_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
NORMALIZED_RECIPIENT_RE = re.compile(r"^[a-z0-9_-]{1,64}$")

MESSAGE_TYPES = {
    "task_request",
    "task_response",
    "action_proposal",
    "validation_error",
    "status_update",
    "reducer_decision",
}

REDUCER_OUTCOMES = {
    "accepted",
    "needs_revision",
    "conflict_detected",
    "ready_for_next",
    "blocked",
}

ENTRY_TYPES = {
    "artifact_accepted",
    "artifact_rejected",
    "artifact_processed",
    "reducer_decision",
    "movement_record",
}


class BClawError(ValueError):
    pass


def is_canonical_json_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return True
    if isinstance(value, int) and not isinstance(value, bool):
        return True
    if isinstance(value, str):
        return True
    if isinstance(value, float):
        return False
    if isinstance(value, list):
        return all(is_canonical_json_value(v) for v in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and is_canonical_json_value(v) for k, v in value.items())
    return False


def require_canonical(value: Any) -> None:
    if not is_canonical_json_value(value):
        raise BClawError("non-canonical JSON: floats, non-string keys, or unsupported objects are forbidden")


def canonical_serialize(value: Any) -> str:
    require_canonical(value)
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_serialize(value).encode("utf-8")).hexdigest()


def valid_utc_z(value: Any) -> bool:
    return isinstance(value, str) and UTC_Z_RE.fullmatch(value) is not None


def fresh(value: dict[str, Any]) -> dict[str, Any]:
    require_canonical(value)
    return copy.deepcopy(value)


def require_fields(raw: dict[str, Any], allowed: set[str], required: set[str]) -> None:
    unknown = set(raw) - allowed
    if unknown:
        raise BClawError(f"unknown fields rejected: {sorted(unknown)}")
    missing = required - set(raw)
    if missing:
        raise BClawError(f"missing required fields: {sorted(missing)}")


def require_nonempty_string(raw: dict[str, Any], field: str) -> None:
    if not isinstance(raw[field], str) or not raw[field].strip():
        raise BClawError(f"{field} must be non-empty string")


def validate_agent_envelope(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise BClawError("AgentEnvelope must be object")

    allowed = {
        "protocol_version", "task_id", "sender", "recipient", "message_type",
        "authority_status", "payload", "constraints", "expected_response_schema",
        "created_at", "parent_task_id", "trace_id",
    }
    required = {
        "protocol_version", "task_id", "sender", "recipient", "message_type",
        "authority_status", "payload", "created_at", "trace_id",
    }
    require_fields(raw, allowed, required)

    if raw["protocol_version"] != "agent_protocol.v0.1":
        raise BClawError("protocol_version must be agent_protocol.v0.1")
    if raw["authority_status"] != "non_authoritative":
        raise BClawError("authority_status must be non_authoritative")
    if raw["message_type"] not in MESSAGE_TYPES:
        raise BClawError("invalid message_type")
    if raw["sender"] == raw["recipient"]:
        raise BClawError("self-routing rejected")

    for field in ("task_id", "sender", "recipient", "trace_id"):
        require_nonempty_string(raw, field)

    if not isinstance(raw["payload"], dict):
        raise BClawError("payload must be object")
    if not valid_utc_z(raw["created_at"]):
        raise BClawError("created_at must be strict UTC Z timestamp")

    if "constraints" in raw and raw["constraints"] is not None and not isinstance(raw["constraints"], list):
        raise BClawError("constraints must be list or null")
    if "expected_response_schema" in raw and raw["expected_response_schema"] is not None and not isinstance(raw["expected_response_schema"], dict):
        raise BClawError("expected_response_schema must be object or null")
    if "parent_task_id" in raw and raw["parent_task_id"] is not None and not isinstance(raw["parent_task_id"], str):
        raise BClawError("parent_task_id must be string or null")

    return fresh(raw)


def validate_reducer_decision(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise BClawError("ReducerDecision must be object")

    allowed = {
        "record_type", "trace_id", "task_id", "outcome", "reason",
        "input_artifact_hashes", "next_recipient", "next_message_type",
        "authority_status", "created_at",
    }
    required = {
        "record_type", "trace_id", "task_id", "outcome", "reason",
        "input_artifact_hashes", "authority_status", "created_at",
    }
    require_fields(raw, allowed, required)

    if raw["record_type"] != "reducer_decision.v0.1":
        raise BClawError("record_type must be reducer_decision.v0.1")
    if raw["authority_status"] != "non_authoritative":
        raise BClawError("authority_status must be non_authoritative")
    if raw["outcome"] not in REDUCER_OUTCOMES:
        raise BClawError("invalid reducer outcome")

    for field in ("trace_id", "task_id", "reason"):
        require_nonempty_string(raw, field)

    if not isinstance(raw["input_artifact_hashes"], list) or any(not isinstance(x, str) for x in raw["input_artifact_hashes"]):
        raise BClawError("input_artifact_hashes must be list of strings")

    if "next_recipient" in raw and raw["next_recipient"] is not None and not isinstance(raw["next_recipient"], str):
        raise BClawError("next_recipient must be string or absent")
    if "next_message_type" in raw and raw["next_message_type"] is not None and raw["next_message_type"] not in MESSAGE_TYPES:
        raise BClawError("next_message_type invalid")

    if not valid_utc_z(raw["created_at"]):
        raise BClawError("created_at must be strict UTC Z timestamp")

    return fresh(raw)


def next_sequence_number(ledger_path: str | Path) -> int:
    entries = read_ledger(ledger_path)
    if not entries:
        return 1
    return entries[-1]["sequence_number"] + 1


def append_ledger_entry(ledger_path: str | Path, entry: dict[str, Any]) -> str:
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not isinstance(entry, dict):
        raise BClawError("ledger entry must be object")

    allowed = {
        "sequence_number", "entry_type", "artifact_type", "artifact_hash",
        "artifact", "source_path", "target_path", "reason", "created_at",
        "authority_status",
    }
    required = {"sequence_number", "entry_type", "artifact_hash", "created_at", "authority_status"}
    require_fields(entry, allowed, required)

    if entry["entry_type"] not in ENTRY_TYPES:
        raise BClawError("invalid ledger entry_type")
    if not isinstance(entry["sequence_number"], int) or isinstance(entry["sequence_number"], bool) or entry["sequence_number"] < 1:
        raise BClawError("sequence_number must be positive integer")
    if entry["authority_status"] != "non_authoritative":
        raise BClawError("ledger authority_status must be non_authoritative")
    if not isinstance(entry["artifact_hash"], str) or not entry["artifact_hash"].strip():
        raise BClawError("artifact_hash must be non-empty string")
    if not valid_utc_z(entry["created_at"]):
        raise BClawError("created_at must be strict UTC Z timestamp")

    existing = read_ledger(path)
    if existing and entry["sequence_number"] <= existing[-1]["sequence_number"]:
        raise BClawError("ledger append must be strictly monotonic")

    line = canonical_serialize(entry)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return entry["artifact_hash"]


def read_ledger(ledger_path: str | Path) -> list[dict[str, Any]]:
    path = Path(ledger_path)
    if not path.exists():
        return []

    out = []
    previous = 0
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            obj = json.loads(line)
            require_canonical(obj)
            seq = obj.get("sequence_number")
            if not isinstance(seq, int) or isinstance(seq, bool) or seq <= previous:
                raise BClawError(f"ledger sequence error at line {line_number}")
            previous = seq
            out.append(obj)
    return out


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise BClawError("JSON artifact must be object")
    return obj


def write_json_atomic(path: str | Path, obj: dict[str, Any]) -> str:
    require_canonical(obj)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(canonical_serialize(obj) + "\n", encoding="utf-8")
    tmp.replace(path)
    return sha256_json(obj)


def accept_pending_envelope(path: str | Path, root: str | Path = "agent_bus") -> dict[str, Any]:
    """Validate pending envelope, move to processed, append ledger. No routing/execution."""
    root = Path(root)
    path = Path(path)
    raw = load_json(path)
    env = validate_agent_envelope(raw)
    artifact_hash = sha256_json(env)

    target = root / "envelopes" / "processed" / path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(target))

    ledger = root / "ledger" / "main.jsonl"
    append_ledger_entry(ledger, {
        "sequence_number": next_sequence_number(ledger),
        "entry_type": "artifact_processed",
        "artifact_type": "agent_envelope.v0.1",
        "artifact_hash": artifact_hash,
        "source_path": str(path),
        "target_path": str(target),
        "created_at": env["created_at"],
        "authority_status": "non_authoritative",
    })
    return env


def reject_pending_envelope(path: str | Path, reason: str, root: str | Path = "agent_bus") -> None:
    """Move invalid envelope to rejected and append rejection fact."""
    root = Path(root)
    path = Path(path)
    target = root / "envelopes" / "rejected" / path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(target))

    ledger = root / "ledger" / "main.jsonl"
    append_ledger_entry(ledger, {
        "sequence_number": next_sequence_number(ledger),
        "entry_type": "artifact_rejected",
        "artifact_hash": sha256_json({"path": str(path), "reason": reason}),
        "source_path": str(path),
        "target_path": str(target),
        "reason": reason,
        "created_at": "2026-05-19T00:00:00Z",
        "authority_status": "non_authoritative",
    })


def reduce_agent_responses(responses: list[dict[str, Any]], created_at: str) -> dict[str, Any]:
    """Deterministic reducer v0.1.

    This proposes coordination state only. It does not route, execute, edit files,
    call models, or mutate ledgers.
    """
    if not responses:
        raise BClawError("responses required")
    if not valid_utc_z(created_at):
        raise BClawError("created_at must be strict UTC Z timestamp")

    envs = [validate_agent_envelope(r) for r in responses]
    trace_ids = {e["trace_id"] for e in envs}
    task_ids = {e["task_id"] for e in envs}
    hashes = [sha256_json(e) for e in envs]

    if len(trace_ids) != 1 or len(task_ids) != 1:
        outcome = "conflict_detected"
        reason = "responses disagree on trace_id or task_id"
    else:
        statuses = [e["payload"].get("status") for e in envs if isinstance(e.get("payload"), dict)]
        if any(s == "blocked" for s in statuses):
            outcome = "blocked"
            reason = "at least one response reports blocked"
        elif any(s == "needs_revision" for s in statuses):
            outcome = "needs_revision"
            reason = "at least one response requests revision"
        elif all(s in ("accepted", "ready_for_next") for s in statuses):
            outcome = "ready_for_next"
            reason = "all responses accepted or ready"
        else:
            outcome = "accepted"
            reason = "responses validated without blocking conflict"

    first = envs[0]
    return validate_reducer_decision({
        "record_type": "reducer_decision.v0.1",
        "trace_id": first["trace_id"],
        "task_id": first["task_id"],
        "outcome": outcome,
        "reason": reason,
        "input_artifact_hashes": hashes,
        "authority_status": "non_authoritative",
        "created_at": created_at,
    })


def replay_state(ledger_path: str | Path) -> dict[str, Any]:
    entries = read_ledger(ledger_path)
    return {
        "entry_count": len(entries),
        "last_sequence_number": entries[-1]["sequence_number"] if entries else 0,
        "accepted": [e for e in entries if e["entry_type"] == "artifact_accepted"],
        "processed": [e for e in entries if e["entry_type"] == "artifact_processed"],
        "rejected": [e for e in entries if e["entry_type"] == "artifact_rejected"],
        "reducer_decisions": [e for e in entries if e["entry_type"] == "reducer_decision"],
    }


def bus_status(root: str | Path = "agent_bus") -> dict[str, int]:
    root = Path(root)
    folders = [
        "envelopes/pending",
        "envelopes/processed",
        "envelopes/rejected",
        "proposals",
        "routing",
        "reducer",
    ]
    counts = {}
    for name in folders:
        folder = root / name
        counts[name] = len(list(folder.glob("*.json"))) if folder.exists() else 0
    ledger = root / "ledger" / "main.jsonl"
    counts["ledger_entries"] = len(read_ledger(ledger))
    return counts


def route_envelope(
    raw_envelope: dict,
    root_dir: str = "agent_bus",
) -> tuple[str, str]:
    """
    Deterministically route a validated AgentEnvelope into a recipient inbox.

    Invariants:
    - Uses existing validate_agent_envelope() boundary
    - Does not mutate caller input
    - Uses canonical serialization only
    - Uses deterministic recipient normalization
    - Uses existing write_json_atomic()
    - No concurrency
    - No dynamic routing config
    - No model calls
    """
    envelope = validate_agent_envelope(raw_envelope)

    recipient = envelope["recipient"].strip().lower()

    if not NORMALIZED_RECIPIENT_RE.fullmatch(recipient):
        raise BClawError(f"invalid recipient: {recipient!r}")

    canonical = canonical_serialize(envelope)

    short_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    task_id = envelope["task_id"]

    inbox_path = (
        Path(root_dir)
        / "inboxes"
        / recipient
        / f"{task_id}_{short_hash}.json"
    )

    file_hash = write_json_atomic(inbox_path, envelope)

    return str(inbox_path), file_hash
