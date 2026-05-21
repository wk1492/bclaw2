"""
tests/unit/test_cognitive_transaction.py

Unit tests for cognitive_transaction.CognitiveTransaction.

Invariants under test:
  1. Clean transaction: all staged records written in order, hash chain intact
  2. Exception inside with-block: ledger unchanged (byte-identical)
  3. Partial staging + exception: nothing written
  4. Gate records precede transcript in committed output
  5. staged_count reflects staged records accurately
  6. Two sequential transactions on the same ledger chain correctly
  7. run_single_turn rollback on model failure: ledger unchanged
  8. validate_transcript_event failure: ledger unchanged
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from cognitive_transaction import CognitiveTransaction
from conversation_runner import run_single_turn
from ledger_writer import verify_ledger
from transcript_ledger import load_ledger_lines, replay_transcript_events
from transcript_event import make_transcript_event
from transcript_validator import validate_transcript_event


_RUN_ID = "run_txn_test_001"
_SENDER = "agent_a"
_RECIPIENT = "agent_b"


def _gate(n: int, run_id: str = _RUN_ID) -> dict:
    return {
        "event_type": "model_call_record",
        "run_id": run_id,
        "seq": n,
    }


def _event(run_id: str = _RUN_ID) -> dict:
    return make_transcript_event(
        run_id=run_id,
        sender=_SENDER,
        recipient=_RECIPIENT,
        role="proposal",
        content=f"Content for {run_id}.",
        created_at="2026-05-20T10:00:00+00:00",
        metadata={"provenance": {"prompt_hash": "a" * 64}},
    )


# ── 1. Clean commit writes all staged records ──────────────────────────────────

def test_clean_commit_writes_gate_records(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    with CognitiveTransaction(ledger) as txn:
        txn.stage_gate(_gate(1))
        txn.stage_gate(_gate(2))
    lines = load_ledger_lines(ledger)
    assert len(lines) == 2
    assert lines[0]["event_type"] == "model_call_record"
    assert lines[1]["event_type"] == "model_call_record"


def test_clean_commit_writes_transcript_event(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    ev = _event()
    with CognitiveTransaction(ledger) as txn:
        txn.stage_gate(_gate(1))
        txn.stage_transcript(ev)
    lines = load_ledger_lines(ledger)
    assert len(lines) == 2
    assert lines[-1]["event_type"] == "transcript.message"


def test_clean_commit_stage_order_preserved(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    ev = _event()
    with CognitiveTransaction(ledger) as txn:
        txn.stage_gate({"event_type": "model_call_record", "seq": 1})
        txn.stage_gate({"event_type": "model_output_record", "seq": 2})
        txn.stage_gate({"event_type": "routing_decision_record", "seq": 3})
        txn.stage_transcript(ev)
    types = [ln["event_type"] for ln in load_ledger_lines(ledger)]
    assert types == [
        "model_call_record",
        "model_output_record",
        "routing_decision_record",
        "transcript.message",
    ]


# ── 2. Exception inside with-block: ledger unchanged ──────────────────────────

def test_exception_rollback_leaves_empty_ledger(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    with pytest.raises(RuntimeError):
        with CognitiveTransaction(ledger) as txn:
            txn.stage_gate(_gate(1))
            txn.stage_gate(_gate(2))
            raise RuntimeError("speculative failure")
    assert not ledger.exists() or ledger.read_bytes() == b""


def test_exception_rollback_leaves_existing_ledger_unchanged(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    # Populate ledger with one record before the transaction
    with CognitiveTransaction(ledger) as txn:
        txn.stage_gate({"event_type": "prior_record", "run_id": "before"})
    before_bytes = ledger.read_bytes()

    with pytest.raises(ValueError):
        with CognitiveTransaction(ledger) as txn:
            txn.stage_gate(_gate(1))
            raise ValueError("rollback me")

    assert ledger.read_bytes() == before_bytes


def test_exception_mid_staging_rollback(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    with pytest.raises(KeyError):
        with CognitiveTransaction(ledger) as txn:
            txn.stage_gate(_gate(1))
            txn.stage_gate(_gate(2))
            raise KeyError("mid-stage failure")
    assert not ledger.exists() or ledger.read_bytes() == b""


# ── 3. staged_count property ─────────────────────────────────────────────────

def test_staged_count_increments_on_stage(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    with CognitiveTransaction(ledger) as txn:
        assert txn.staged_count == 0
        txn.stage_gate(_gate(1))
        assert txn.staged_count == 1
        txn.stage_gate(_gate(2))
        assert txn.staged_count == 2
        txn.stage_transcript(_event())
        assert txn.staged_count == 3


# ── 4. Hash chain integrity after commit ──────────────────────────────────────

def test_hash_chain_valid_after_single_transaction(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    with CognitiveTransaction(ledger) as txn:
        txn.stage_gate(_gate(1))
        txn.stage_gate(_gate(2))
        txn.stage_gate(_gate(3))
        txn.stage_transcript(_event())
    status = verify_ledger(ledger)
    assert status["ok"] is True
    assert status["count"] == 4


def test_hash_chain_valid_after_two_sequential_transactions(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    with CognitiveTransaction(ledger) as txn:
        txn.stage_gate(_gate(1, run_id="run_001"))
        txn.stage_transcript(_event("run_001"))
    with CognitiveTransaction(ledger) as txn:
        txn.stage_gate(_gate(1, run_id="run_002"))
        ev2 = make_transcript_event(
            run_id="run_002", sender=_SENDER, recipient=_RECIPIENT,
            role="proposal", content="Second content.",
            created_at="2026-05-20T11:00:00+00:00",
            metadata={"provenance": {"prompt_hash": "b" * 64}},
        )
        txn.stage_transcript(ev2)
    status = verify_ledger(ledger)
    assert status["ok"] is True
    assert status["count"] == 4


# ── 5. Rollback between two transactions leaves first intact ───────────────────

def test_rollback_between_transactions_preserves_first(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    with CognitiveTransaction(ledger) as txn:
        txn.stage_gate({"event_type": "model_call_record", "run_id": "run_001"})
    after_first = ledger.read_bytes()

    with pytest.raises(RuntimeError):
        with CognitiveTransaction(ledger) as txn:
            txn.stage_gate({"event_type": "model_call_record", "run_id": "run_002"})
            raise RuntimeError("second fails")

    assert ledger.read_bytes() == after_first


# ── 6. Integration: run_single_turn rollback on model failure ─────────────────

def test_run_single_turn_rollback_on_model_error(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    with patch("conversation_runner.run_proposal", side_effect=RuntimeError("model down")):
        with pytest.raises(RuntimeError):
            run_single_turn("Input.", ledger, _RUN_ID, _SENDER, _RECIPIENT)
    # Nothing should have been written — model_call_record was staged but not committed
    assert not ledger.exists() or load_ledger_lines(ledger) == []


# ── 7. Integration: validate_transcript_event failure rolls back ───────────────

def test_run_single_turn_rollback_on_validation_error(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    from transcript_validator import TranscriptValidationError

    with patch("conversation_runner.validate_transcript_event",
               side_effect=TranscriptValidationError("invalid")):
        with pytest.raises(TranscriptValidationError):
            run_single_turn("Input.", ledger, _RUN_ID, _SENDER, _RECIPIENT)
    assert not ledger.exists() or load_ledger_lines(ledger) == []
