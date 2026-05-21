"""
test_conversation_runner.py

Structural acceptance tests for conversation_runner.run_single_turn and
run_parallel_turns.  No semantic answer assertions. No live model calls.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from conversation_runner import (
    build_history_summary,
    run_conversation,
    run_parallel_turns,
    run_single_turn,
)
from ledger_writer import verify_ledger
from transcript_event import canonical_json
from transcript_ledger import load_ledger_lines, replay_transcript_events

_RUN_ID = "run_cr_test_001"
_SENDER = "agent_a"
_RECIPIENT = "agent_b"
_INPUT = "Analyze: deterministic cognition loop."

_GATE_SEQUENCE = (
    "model_call_record",
    "model_output_record",
    "routing_decision_record",
    "transcript.message",
)


def _single_turn(tmp_path, *, run_id=_RUN_ID, include_history=True, suffix="ledger.jsonl"):
    ledger = tmp_path / suffix
    result = run_single_turn(
        _INPUT, ledger, run_id, _SENDER, _RECIPIENT,
        include_history=include_history,
    )
    return result, ledger


# ── 1. Three-record gate order exact ─────────────────────────────────────────

def test_gate_order_is_exact(tmp_path):
    _, ledger = _single_turn(tmp_path)
    lines = load_ledger_lines(ledger)
    event_types = [ln.get("event_type") for ln in lines]

    # Must contain all four in sequence; no extra gate records interleaved
    assert len(event_types) == 4, f"expected 4 ledger records, got {event_types}"
    assert tuple(event_types) == _GATE_SEQUENCE, (
        f"gate order wrong: {event_types}"
    )


def test_transcript_message_is_last(tmp_path):
    _, ledger = _single_turn(tmp_path)
    lines = load_ledger_lines(ledger)
    assert lines[-1]["event_type"] == "transcript.message"


def test_model_call_record_run_id(tmp_path):
    _, ledger = _single_turn(tmp_path)
    lines = load_ledger_lines(ledger)
    gate = next(ln for ln in lines if ln["event_type"] == "model_call_record")
    assert gate["run_id"] == _RUN_ID


# ── 2. Transcript content equals model output ─────────────────────────────────

def test_transcript_content_equals_result_content(tmp_path):
    result, ledger = _single_turn(tmp_path)
    events = replay_transcript_events(ledger)
    assert len(events) == 1
    assert events[0]["content"] == result["content"]


def test_transcript_content_output_hash_matches(tmp_path):
    result, ledger = _single_turn(tmp_path)
    events = replay_transcript_events(ledger)
    content = events[0]["content"]
    expected = hashlib.sha256(content.encode()).hexdigest()
    assert result["provenance"]["output_hash"] == expected


# ── 3. Prompt preserved in metadata/provenance ────────────────────────────────

def test_prompt_hash_in_event_metadata(tmp_path):
    _, ledger = _single_turn(tmp_path)
    events = replay_transcript_events(ledger)
    provenance = events[0]["metadata"]["provenance"]
    assert "prompt_hash" in provenance
    assert isinstance(provenance["prompt_hash"], str)
    assert len(provenance["prompt_hash"]) == 64  # sha256 hex


def test_prompt_not_in_transcript_content(tmp_path):
    _, ledger = _single_turn(tmp_path)
    events = replay_transcript_events(ledger)
    # Content is model output; raw input_text must not appear verbatim in content
    assert _INPUT not in events[0]["content"]


def test_runner_output_in_provenance(tmp_path):
    _, ledger = _single_turn(tmp_path)
    events = replay_transcript_events(ledger)
    runner_out = events[0]["metadata"]["provenance"]["runner_output"]
    for field in ("run_id", "sender", "recipient", "role",
                  "model_name", "prompt_hash", "content", "output_hash"):
        assert field in runner_out, f"runner_output missing {field!r}"


# ── 4. run_id must be caller-supplied ────────────────────────────────────────

def test_run_id_echoed_unchanged(tmp_path):
    result, _ = _single_turn(tmp_path)
    assert result["run_id"] == _RUN_ID


def test_run_id_propagated_to_transcript(tmp_path):
    _, ledger = _single_turn(tmp_path)
    assert replay_transcript_events(ledger)[0]["run_id"] == _RUN_ID


def test_run_id_empty_raises(tmp_path):
    with pytest.raises((ValueError, TypeError)):
        run_single_turn(_INPUT, tmp_path / "l.jsonl", "", _SENDER, _RECIPIENT)


def test_run_id_none_raises(tmp_path):
    with pytest.raises((ValueError, TypeError)):
        run_single_turn(_INPUT, tmp_path / "l.jsonl", None, _SENDER, _RECIPIENT)


# ── 5. Replay must not call model_runner ─────────────────────────────────────

def test_run_conversation_does_not_call_model_runner(tmp_path):
    _, ledger = _single_turn(tmp_path)
    with patch("conversation_runner.run_proposal") as mock:
        run_conversation(ledger)
    mock.assert_not_called()


def test_replay_transcript_events_does_not_call_model_runner(tmp_path):
    _, ledger = _single_turn(tmp_path)
    with patch("conversation_runner.run_proposal") as mock:
        replay_transcript_events(ledger)
    mock.assert_not_called()


# ── 6. Byte-identical via canonical_json ──────────────────────────────────────
# history_summary is excluded: it contains descriptive_timestamp from
# LedgerWriter.utc_now() which is a wall-clock value and is intentionally
# non-deterministic at the ledger layer. All semantic fields are deterministic.

def test_repeated_runs_canonical_json_identical(tmp_path):
    r1 = run_single_turn(_INPUT, tmp_path / "a.jsonl", _RUN_ID, _SENDER, _RECIPIENT,
                         include_history=False)
    r2 = run_single_turn(_INPUT, tmp_path / "b.jsonl", _RUN_ID, _SENDER, _RECIPIENT,
                         include_history=False)
    assert canonical_json(r1) == canonical_json(r2)


def test_repeated_runs_message_id_identical(tmp_path):
    r1 = run_single_turn(_INPUT, tmp_path / "a.jsonl", _RUN_ID, _SENDER, _RECIPIENT)
    r2 = run_single_turn(_INPUT, tmp_path / "b.jsonl", _RUN_ID, _SENDER, _RECIPIENT)
    assert r1["message_id"] == r2["message_id"]


def test_repeated_runs_replay_audit_identical(tmp_path):
    r1 = run_single_turn(_INPUT, tmp_path / "a.jsonl", _RUN_ID, _SENDER, _RECIPIENT,
                         include_history=False)
    r2 = run_single_turn(_INPUT, tmp_path / "b.jsonl", _RUN_ID, _SENDER, _RECIPIENT,
                         include_history=False)
    assert r1["replay_audit"] == r2["replay_audit"]


# ── 7. include_history=False omits history_summary ───────────────────────────

def test_include_history_false_key_absent(tmp_path):
    result, _ = _single_turn(tmp_path, include_history=False)
    assert "history_summary" not in result


def test_include_history_true_key_present(tmp_path):
    result, _ = _single_turn(tmp_path, include_history=True)
    assert "history_summary" in result
    assert isinstance(result["history_summary"], list)


def test_include_history_flag_echoed(tmp_path):
    r_f = run_single_turn(_INPUT, tmp_path / "f.jsonl", _RUN_ID, _SENDER, _RECIPIENT,
                          include_history=False)
    r_t = run_single_turn(_INPUT, tmp_path / "t.jsonl", _RUN_ID, _SENDER, _RECIPIENT,
                          include_history=True)
    assert r_f["include_history"] is False
    assert r_t["include_history"] is True


# ── 8. history_summary deterministic if included ─────────────────────────────

def test_history_summary_deterministic_same_events():
    events = [
        {
            "message_id": f"tmsg_{i:024d}", "role": "proposal",
            "sender": f"agent_{i}", "content": f"content_{i}",
            "created_at": f"2026-05-20T10:{i:02d}:00Z",
            "event_type": "transcript.message",
            "timestamp": "2026-05-20T23:00:00Z",
            "event_hash": "a" * 64, "event_id": f"e{i}",
            "previous_hash": "0" * 64, "rolling_hash": "b" * 64,
        }
        for i in range(5)
    ]
    s1 = build_history_summary(events)
    s2 = build_history_summary(events)
    assert s1 == s2


def test_history_summary_tail_truncation():
    events = [
        {
            "message_id": f"tmsg_{i:024d}", "role": "proposal",
            "sender": f"agent_{i}", "content": f"c{i}",
            "created_at": f"2026-05-20T10:{i:02d}:00Z",
            "event_type": "transcript.message",
            "timestamp": "2026-05-20T23:00:00Z",
            "event_hash": "a" * 64, "event_id": f"e{i}",
            "previous_hash": "0" * 64, "rolling_hash": "b" * 64,
        }
        for i in range(15)
    ]
    summary = build_history_summary(events, max_events=4)
    assert len(summary) == 4
    # tail: last 4 senders are agent_11 through agent_14
    assert summary[0]["sender"] == "agent_11"
    assert summary[-1]["sender"] == "agent_14"


def test_history_summary_no_timestamp_field(tmp_path):
    result, _ = _single_turn(tmp_path, include_history=True)
    for entry in result["history_summary"]:
        assert "timestamp" not in entry


# ── 9. Ledger hash-chain verifies ────────────────────────────────────────────

def test_ledger_chain_ok_single_turn(tmp_path):
    result, _ = _single_turn(tmp_path)
    assert result["chain_ok"] is True


def test_verify_ledger_ok_after_turn(tmp_path):
    _, ledger = _single_turn(tmp_path)
    status = verify_ledger(ledger)
    assert status["ok"] is True
    assert len(status["failures"]) == 0


def test_verify_ledger_two_turns(tmp_path):
    ledger = tmp_path / "two.jsonl"
    run_single_turn(_INPUT, ledger, "run_001", _SENDER, _RECIPIENT)
    run_single_turn("Second input.", ledger, "run_002", _SENDER, _RECIPIENT)
    status = verify_ledger(ledger)
    assert status["ok"] is True
    assert status["count"] == 8  # (3 gate + 1 transcript) × 2 turns


# ── 10. No baseline artifacts changed ────────────────────────────────────────

def test_no_baseline_artifacts_mutated(tmp_path):
    baseline_dir = Path("artifacts/baselines")
    if not baseline_dir.exists():
        pytest.skip("artifacts/baselines not present")

    before = {f.name: f.read_bytes() for f in sorted(baseline_dir.glob("*")) if f.is_file()}
    _single_turn(tmp_path)
    for name, content in before.items():
        assert (baseline_dir / name).read_bytes() == content, (
            f"baseline mutated: {name}"
        )


def test_no_global_execution_ledger_written(tmp_path):
    # run_single_turn must write only to the caller-supplied ledger_path
    global_ledger = Path("execution_ledger.jsonl")
    size_before = global_ledger.stat().st_size if global_ledger.exists() else -1
    _single_turn(tmp_path)
    size_after = global_ledger.stat().st_size if global_ledger.exists() else -1
    assert size_before == size_after, "run_single_turn must not write to execution_ledger.jsonl"


# ── 11. run_parallel_turns ────────────────────────────────────────────────────

_PARALLEL_TURNS = [
    {"run_id": f"run_p_{i:03d}", "sender": "agent_a", "recipient": "agent_b",
     "input_text": f"Parallel input {i}."}
    for i in range(4)
]


def test_parallel_turns_returns_expected_keys(tmp_path):
    result = run_parallel_turns(_PARALLEL_TURNS, tmp_path / "p.jsonl")
    for key in ("turns_requested", "turns_completed", "turns_failed",
                "failed", "results", "event_count", "replay_audit",
                "chain_ok", "_instrumentation"):
        assert key in result, f"run_parallel_turns result missing {key!r}"


def test_parallel_turns_all_completed(tmp_path):
    result = run_parallel_turns(_PARALLEL_TURNS, tmp_path / "p.jsonl")
    assert result["turns_requested"] == 4
    assert result["turns_completed"] == 4
    assert result["turns_failed"] == 0
    assert result["failed"] == {}


def test_parallel_turns_gate_order_per_turn(tmp_path):
    run_parallel_turns(_PARALLEL_TURNS, tmp_path / "p.jsonl")
    lines = load_ledger_lines(tmp_path / "p.jsonl")
    types = [ln.get("event_type") for ln in lines]
    assert len(types) == 16, f"expected 16 records (4 per turn), got {len(types)}"
    for i in range(4):
        block = types[i * 4:(i + 1) * 4]
        assert tuple(block) == _GATE_SEQUENCE, f"turn {i} gate order wrong: {block}"


def test_parallel_turns_append_order_deterministic(tmp_path):
    result = run_parallel_turns(_PARALLEL_TURNS, tmp_path / "p.jsonl")
    indices = [r["turn_index"] for r in result["results"]]
    assert indices == sorted(indices), "results not in deterministic turn-index order"


def test_parallel_turns_repeated_runs_canonical_identical(tmp_path):
    turns = [
        {"run_id": f"run_det_{i}", "sender": "ag_a", "recipient": "ag_b",
         "input_text": f"Det input {i}."}
        for i in range(3)
    ]
    r1 = run_parallel_turns(turns, tmp_path / "det_a.jsonl")
    r2 = run_parallel_turns(turns, tmp_path / "det_b.jsonl")

    # Strip non-canonical _instrumentation before comparing
    r1_canon = {k: v for k, v in r1.items() if k != "_instrumentation"}
    r2_canon = {k: v for k, v in r2.items() if k != "_instrumentation"}
    assert canonical_json(r1_canon) == canonical_json(r2_canon)


def test_parallel_turns_chain_ok(tmp_path):
    result = run_parallel_turns(_PARALLEL_TURNS, tmp_path / "p.jsonl")
    assert result["chain_ok"] is True


def test_parallel_turns_replay_no_model_call(tmp_path):
    run_parallel_turns(_PARALLEL_TURNS, tmp_path / "p.jsonl")
    with patch("conversation_runner.run_proposal") as mock:
        replay_transcript_events(tmp_path / "p.jsonl")
    mock.assert_not_called()


def test_parallel_turns_empty_raises(tmp_path):
    with pytest.raises((ValueError, TypeError)):
        run_parallel_turns([], tmp_path / "empty.jsonl")
