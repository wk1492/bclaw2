"""Tests for bclaw2_demo.py — BCLAW2 minimal cognition loop demo."""
import json
import tempfile
from pathlib import Path

import pytest

from bclaw2_demo import (
    PROTOCOL,
    _ADAPTER,
    append_to_transcript,
    load_transcript,
    make_envelope,
    replay_demo,
    run_demo,
    worker_process,
)


# ── envelope contract ──────────────────────────────────────────────────────────

def test_make_envelope_required_fields():
    env = make_envelope("task_request", "a", "b", "T-001", {"x": 1})
    assert set(env.keys()) == {"protocol", "type", "sender", "recipient", "task_id", "payload"}


def test_make_envelope_protocol_value():
    env = make_envelope("task_request", "a", "b", "T-001", {})
    assert env["protocol"] == PROTOCOL


def test_make_envelope_payload_preserved():
    payload = {"prompt": "hello", "flags": [1, 2]}
    env = make_envelope("task_request", "a", "b", "T-001", payload)
    assert env["payload"] == payload


# ── worker determinism ─────────────────────────────────────────────────────────

def test_worker_process_is_deterministic():
    assert worker_process("same prompt") == worker_process("same prompt")


def test_worker_process_changes_on_different_input():
    assert worker_process("prompt A") != worker_process("prompt B")


def test_worker_process_returns_nonempty_string():
    result = worker_process("test input")
    assert isinstance(result, str) and result.strip()


# ── transcript I/O ─────────────────────────────────────────────────────────────

def test_append_and_load_roundtrip():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    env = make_envelope("task_request", "a", "b", "T-001", {"k": "v"})
    append_to_transcript(env, path)
    loaded = load_transcript(path)
    assert len(loaded) == 1
    assert loaded[0] == env


def test_transcript_lines_are_canonical_json():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    env = make_envelope("task_response", "worker", "orchestrator", "T-002", {"result": "ok"})
    append_to_transcript(env, path)
    raw = path.read_text().strip()
    assert raw == json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":"))


def test_load_transcript_empty_if_missing():
    assert load_transcript(Path("/tmp/nonexistent_bclaw2_test_xyz.jsonl")) == []


# ── full loop ──────────────────────────────────────────────────────────────────

def test_run_demo_returns_task_response():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    result = run_demo(transcript_path=path)
    assert result["type"] == "task_response"
    assert result["sender"] == "worker"
    assert result["recipient"] == "orchestrator"


def test_run_demo_produces_two_envelopes():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    run_demo(transcript_path=path)
    envelopes = load_transcript(path)
    assert len(envelopes) == 2


def test_run_demo_envelope_types():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    run_demo(transcript_path=path)
    envelopes = load_transcript(path)
    types = [e["type"] for e in envelopes]
    assert types == ["task_request", "task_response"]


def test_run_demo_adapter_reported():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    result = run_demo(transcript_path=path)
    assert result["payload"]["adapter"] == _ADAPTER


# ── replay ─────────────────────────────────────────────────────────────────────

def test_replay_matches_live_result():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    live = run_demo(transcript_path=path)
    replayed = replay_demo(path)
    assert replayed["payload"]["result"] == live["payload"]["result"]


def test_replay_is_idempotent():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    run_demo(transcript_path=path)
    r1 = replay_demo(path)
    r2 = replay_demo(path)
    assert r1["payload"]["result"] == r2["payload"]["result"]


def test_replay_raises_on_missing_transcript():
    with pytest.raises(ValueError, match="Empty or missing"):
        replay_demo(Path("/tmp/nonexistent_bclaw2_replay_xyz.jsonl"))


def test_replay_raises_on_no_response():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    env = make_envelope("task_request", "a", "b", "T-001", {})
    append_to_transcript(env, path)
    with pytest.raises(ValueError, match="No task_response"):
        replay_demo(path)
