from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from agent_bus.core_comm_v0 import (
    BClawError,
    route_envelope,
    validate_agent_envelope,
)

_BASE: dict = {
    "protocol_version": "agent_protocol.v0.1",
    "task_id": "task-001",
    "sender": "copilot",
    "recipient": "dia",
    "message_type": "task_request",
    "authority_status": "non_authoritative",
    "payload": {},
    "created_at": "2026-05-22T00:00:00Z",
    "trace_id": "trace-001",
}


def _env(**overrides) -> dict:
    return {**_BASE, **overrides}


# 1. successful deterministic routing
def test_successful_routing():
    with tempfile.TemporaryDirectory() as tmp:
        path, file_hash = route_envelope(_env(), root_dir=tmp)
        assert Path(path).exists()
        assert isinstance(file_hash, str) and len(file_hash) == 64


# 2. invalid recipient rejected
def test_invalid_recipient_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(BClawError, match="invalid recipient"):
            route_envelope(_env(recipient="invalid@user"), root_dir=tmp)


# 3. input envelope not mutated
def test_input_not_mutated():
    with tempfile.TemporaryDirectory() as tmp:
        original = _env()
        snapshot = dict(original)
        route_envelope(original, root_dir=tmp)
        assert original == snapshot


# 4. repeated routing returns identical path and hash
def test_repeated_routing_identical():
    with tempfile.TemporaryDirectory() as tmp:
        r1 = route_envelope(_env(), root_dir=tmp)
        r2 = route_envelope(_env(), root_dir=tmp)
        assert r1 == r2


# 5. recipient normalization collapses DIA/dia to same inbox directory
def test_recipient_normalization():
    with tempfile.TemporaryDirectory() as tmp:
        path_upper, _ = route_envelope(_env(recipient="DIA"), root_dir=tmp)
        path_lower, _ = route_envelope(_env(recipient="dia"), root_dir=tmp)
        assert Path(path_upper).parent == Path(path_lower).parent
        assert Path(path_upper).parent.name == "dia"


# 6. canonical JSON bytes written to disk
def test_canonical_json_written():
    with tempfile.TemporaryDirectory() as tmp:
        path, _ = route_envelope(_env(), root_dir=tmp)
        raw = Path(path).read_text(encoding="utf-8")
        parsed = json.loads(raw)
        assert list(parsed.keys()) == sorted(parsed.keys())
        assert ": " not in raw
        assert ", " not in raw
        assert parsed == validate_agent_envelope(_env())


# 7. routing path shape is deterministic
def test_path_shape_deterministic():
    with tempfile.TemporaryDirectory() as tmp:
        path, file_hash = route_envelope(_env(), root_dir=tmp)
        p = Path(path)
        assert p.suffix == ".json"
        assert p.parent.name == "dia"
        assert p.parent.parent.name == "inboxes"
        assert p.name == f"task-001_{file_hash[:16]}.json"


# 8. invalid schema rejected through validate_agent_envelope
def test_invalid_schema_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(BClawError):
            route_envelope(_env(protocol_version="bad"), root_dir=tmp)
        with pytest.raises(BClawError):
            bad = _env()
            del bad["task_id"]
            route_envelope(bad, root_dir=tmp)
        with pytest.raises(BClawError):
            route_envelope(_env(sender="dia", recipient="dia"), root_dir=tmp)
