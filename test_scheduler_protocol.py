import json
import pathlib
import pytest

SCHEDULER_DIR = pathlib.Path(__file__).parent / "scheduler"
SCHEMA_FILES = ["task_packet.json", "agent_result.json", "window_registry.json"]


def _load(name: str) -> tuple[str, dict]:
    raw = (SCHEDULER_DIR / name).read_text()
    return raw, json.loads(raw)


def _validate_required(instance: dict, schema: dict) -> list[str]:
    return [f for f in schema.get("required", []) if f not in instance]


# ── 1. Canonical serialization ────────────────────────────────────────────────

def test_schemas_serialize_canonically():
    for name in SCHEMA_FILES:
        raw, obj = _load(name)
        canon = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert raw == canon, f"{name} is not in canonical form"
        assert not raw.endswith("\n"), f"{name} has trailing newline"


# ── 2. Required fields present in valid instances ─────────────────────────────

def test_task_packet_required_fields():
    _, schema = _load("task_packet.json")
    valid = {
        "move_id": "m01",
        "assigned_agent": "agent_a",
        "objective": "Write the state reducer.",
        "allowed_files": ["transcript_state.py", "test_transcript_state.py"],
        "forbidden_files": ["ledger_writer.py"],
        "autonomy_level": "supervised",
        "stop_condition": "pass-all-tests",
        "requires_human_approval": False,
        "status": "assigned",
    }
    missing = _validate_required(valid, schema)
    assert missing == [], f"Valid packet missing required fields: {missing}"


def test_agent_result_required_fields():
    _, schema = _load("agent_result.json")
    valid = {
        "move_id": "m01",
        "agent": "agent_a",
        "files_changed": ["transcript_state.py"],
        "tests_run": 9,
        "result": "pass",
        "drift_risk": "none",
        "unresolved": [],
        "next_recommended_move": "m02",
    }
    missing = _validate_required(valid, schema)
    assert missing == [], f"Valid result missing required fields: {missing}"


# ── 3. Deterministic ordering ─────────────────────────────────────────────────

def test_deterministic_ordering():
    for name in SCHEMA_FILES:
        _, obj = _load(name)
        first = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for _ in range(50):
            again = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            assert again == first, f"{name} serialization is not deterministic"


# ── 4. Invalid packets rejected ───────────────────────────────────────────────

def test_invalid_packet_rejected():
    _, schema = _load("task_packet.json")
    incomplete = {
        "assigned_agent": "agent_a",
        "objective": "Missing move_id and other required fields.",
        "autonomy_level": "supervised",
        "status": "pending",
    }
    missing = _validate_required(incomplete, schema)
    assert "move_id" in missing
    assert "allowed_files" in missing
    assert "forbidden_files" in missing
    assert "stop_condition" in missing
    assert "requires_human_approval" in missing


# ── 5. Invalid results rejected ───────────────────────────────────────────────

def test_invalid_result_rejected():
    _, schema = _load("agent_result.json")
    incomplete = {
        "move_id": "m01",
        "agent": "agent_a",
        "result": "pass",
    }
    missing = _validate_required(incomplete, schema)
    assert "drift_risk" in missing
    assert "files_changed" in missing
    assert "tests_run" in missing
    assert "unresolved" in missing
    assert "next_recommended_move" in missing


# ── 6. Repeated serialization byte-identical ──────────────────────────────────

def test_repeated_serialization_byte_identical():
    for name in SCHEMA_FILES:
        raw, obj = _load(name)
        for _ in range(100):
            result = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            assert result.encode() == raw.encode(), (
                f"{name}: serialization not byte-identical on repeat"
            )
