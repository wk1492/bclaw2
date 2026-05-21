"""
conversation_runner.py — SUBSTRATE_VERSION=1 single-turn runner and
replay-derived conversation state for BCLAW2.

AUTHORITY BOUNDARY
------------------
history_summary is non-authoritative replay-derived convenience context only.
The canonical record of what happened is always the transcript events in the
ledger — not anything produced here.

THREE-RECORD GATE (mandatory for run_single_turn)
--------------------------------------------------
ModelCallRecord, ModelOutputRecord, and RoutingDecisionRecord are appended to
the ledger before any transcript.message event. This ordering is enforced by
the implementation: gate records are written first via LedgerWriter, then the
transcript event is appended via append_transcript_event which continues the
same hash chain.

Invariants preserved:
- run_id is required and externally supplied; never generated here.
- No wall-clock time, no random, no uuid in semantic paths.
  created_at is derived deterministically from run_id + content hash.
- Prompt/request/model metadata go in metadata["provenance"], not content.
- transcript.message content is the recorded model output.
- history_summary is bounded, deterministic, and non-authoritative.
- "timestamp" (ledger append time) is renamed descriptive_timestamp in all
  views returned to callers.
"""
from __future__ import annotations

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple

from cognitive_transaction import CognitiveTransaction
from ledger_writer import LedgerWriter
from retention_policy import RetentionPolicy, TailRetention
from model_runner import run_proposal
from replay_audit import compute_replay_audit
from substrate_errors import SUBSTRATE_VERSION
from transcript_event import make_transcript_event
from transcript_ledger import (
    append_transcript_event,
    load_ledger_lines,
    replay_transcript_events,
    verify_mixed_ledger,
)
from transcript_validator import validate_transcript_event

# ── types ─────────────────────────────────────────────────────────────────────

class TurnExecutionResult(NamedTuple):
    turn_index: int
    records: list[dict[str, Any]]        # three gate records as written to ledger
    transcript_messages: list[dict[str, Any]]  # transcript.message events appended
    instrumentation: dict[str, Any]      # non-canonical wall-clock floats


# ── constants ──────────────────────────────────────────────────────────────────

DEFAULT_MAX_HISTORY_EVENTS = 10

_LEDGER_INTERNAL_FIELDS = frozenset({
    "event_hash",
    "event_id",
    "previous_hash",
    "rolling_hash",
})

_SUBSTRATE_PROMPT_TEMPLATE = "[SUBSTRATE_VERSION={v}]\nInput: {input_text}"

# ── internal helpers ───────────────────────────────────────────────────────────

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _deterministic_created_at(run_id: str, content: str) -> str:
    """
    Derive a deterministic created_at timestamp from run_id and content.
    No wall-clock time. Same inputs always produce the same timestamp.
    """
    offset = int(_sha256(f"{run_id}:{content}"), 16) % 86400
    epoch = 1747000000 + offset
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _build_prompt(input_text: str) -> str:
    return _SUBSTRATE_PROMPT_TEMPLATE.format(
        v=SUBSTRATE_VERSION, input_text=input_text
    )


def _append_gate_record(record: dict[str, Any], ledger_path: Path) -> dict[str, Any]:
    """Write one gate record into the hash chain. Returns the decorated record."""
    writer = LedgerWriter(ledger_path)
    return writer.append(record)


# ── safe view (non-authoritative) ─────────────────────────────────────────────

def _safe_result_view(event: dict[str, Any]) -> dict[str, Any]:
    """
    Non-authoritative view of a transcript event.

    Strips ledger-internal hash-chain fields. Renames 'timestamp' to
    'descriptive_timestamp' — the wall-clock append time is informational only
    and must never be used for causal ordering or replay reconstruction.
    """
    view: dict[str, Any] = {}
    for k, v in event.items():
        if k in _LEDGER_INTERNAL_FIELDS:
            continue
        if k == "timestamp":
            view["descriptive_timestamp"] = v
        else:
            view[k] = v
    return view


# ── history summary (non-authoritative replay-derived context) ─────────────────

# NON-AUTHORITATIVE replay-derived convenience context.
# Deterministic and bounded only.
# Must never become canonical cognition state.
# Replay truth remains recorded transcript events.

def build_history_summary(
    events: list[dict[str, Any]],
    max_events: int = DEFAULT_MAX_HISTORY_EVENTS,
    retention_policy: RetentionPolicy | None = None,
) -> list[dict[str, Any]]:
    """
    Bounded, deterministic summary of recent transcript events.

    retention_policy controls which events survive. When None, defaults to
    TailRetention(max_events) — the last N events (backward-compatible).
    Any RetentionPolicy implementation may be supplied; it must be pure and
    deterministic (no I/O, no randomness, no wall-clock time).

    The ledger is never pruned. Forgetting is a view-layer operation only.

    - Derived solely from already-replayed transcript events (no I/O).
    - Ordered by topology linearization order from replay_transcript_events.
    - Deterministic: identical input + identical policy → identical output.
    - No randomness, no wall-clock time, no UUIDs introduced.
    - Prior events are never mutated.
    """
    policy = retention_policy if retention_policy is not None else TailRetention(max_events)
    bounded = policy.select(events)
    return [_safe_result_view(e) for e in bounded]


# ── run_single_turn ────────────────────────────────────────────────────────────

def run_single_turn(
    input_text: str,
    ledger_path: str | Path,
    run_id: str,
    sender: str,
    recipient: str,
    model_config: dict[str, Any] | None = None,
    extra_metadata: dict[str, Any] | None = None,
    include_history: bool = True,
) -> dict[str, Any]:
    """
    Execute one turn of the single-agent cognition loop.

    Gate ordering (mandatory):
      1. ModelCallRecord   — before model is called
      2. ModelOutputRecord — after model returns
      3. RoutingDecisionRecord — gate closes
      4. transcript.message — appended last

    run_id is required and must be supplied by the caller. It is echoed
    in the return value and never generated internally.

    Returns a JSON-safe dict. Does not contain 'timestamp'; ledger append
    times are available as 'descriptive_timestamp' in history_summary views.
    """
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id must be a non-empty string supplied by the caller")
    if not isinstance(input_text, str) or not input_text.strip():
        raise ValueError("input_text must be a non-empty string")
    if not isinstance(sender, str) or not sender.strip():
        raise ValueError("sender must be a non-empty string")
    if not isinstance(recipient, str) or not recipient.strip():
        raise ValueError("recipient must be a non-empty string")

    ledger_path = Path(ledger_path)
    cfg = model_config or {}
    model_name = cfg.get("model_name", "stub")
    role = cfg.get("role", "proposal")

    prompt = _build_prompt(input_text)
    prompt_hash = _sha256(prompt)

    with CognitiveTransaction(ledger_path) as txn:
        # Stage Gate 1 before model is called
        txn.stage_gate({
            "event_type": "model_call_record",
            "substrate_version": SUBSTRATE_VERSION,
            "run_id": run_id,
            "sender": sender,
            "recipient": recipient,
            "model_name": model_name,
            "prompt_hash": prompt_hash,
        })

        # Speculative: model call — exception here → ROLLBACK
        runner_payload = run_proposal(
            run_id=run_id,
            sender=sender,
            recipient=recipient,
            role=role,
            prompt=prompt,
            model_name=model_name,
        )
        content = runner_payload["content"]
        output_hash = runner_payload["output_hash"]

        txn.stage_gate({
            "event_type": "model_output_record",
            "substrate_version": SUBSTRATE_VERSION,
            "run_id": run_id,
            "model_name": model_name,
            "output_hash": output_hash,
        })
        txn.stage_gate({
            "event_type": "routing_decision_record",
            "substrate_version": SUBSTRATE_VERSION,
            "run_id": run_id,
            "sender": sender,
            "recipient": recipient,
            "role": role,
        })

        created_at = _deterministic_created_at(run_id, content)
        provenance: dict[str, Any] = {
            "prompt_hash": prompt_hash,
            "model_name": model_name,
            "output_hash": output_hash,
            "substrate_version": SUBSTRATE_VERSION,
            "runner_output": runner_payload,
        }
        if extra_metadata:
            provenance["extra"] = extra_metadata

        event = make_transcript_event(
            run_id=run_id,
            sender=sender,
            recipient=recipient,
            role=role,
            content=content,
            created_at=created_at,
            metadata={"provenance": provenance},
        )

        # Validation before staging — exception here → ROLLBACK
        validate_transcript_event(event)
        txn.stage_transcript(event)
    # COMMIT: all 4 records written atomically

    # ── Replay and audit ──────────────────────────────────────────────────────
    transcript_events = replay_transcript_events(ledger_path)
    replay_audit = compute_replay_audit(transcript_events)
    chain_status = verify_mixed_ledger(ledger_path)

    result: dict[str, Any] = {
        "run_id": run_id,
        "message_id": event["message_id"],
        "content": content,
        "provenance": {
            "prompt_hash": prompt_hash,
            "model_name": model_name,
            "output_hash": output_hash,
            "substrate_version": SUBSTRATE_VERSION,
        },
        "event_count": len(transcript_events),
        "replay_audit": replay_audit,
        "chain_ok": chain_status.get("ok", False),
        "include_history": include_history,
    }

    # NON-AUTHORITATIVE replay-derived convenience context.
    # Deterministic and bounded only.
    # Must never become canonical cognition state.
    # Replay truth remains recorded transcript events.
    if include_history:
        result["history_summary"] = build_history_summary(transcript_events)

    return result


# ── run_parallel_turns ────────────────────────────────────────────────────────
#
# Concurrency model:
#   Phase 1 — concurrent model generation via ThreadPoolExecutor (no I/O)
#   Phase 2 — sort generated results by turn index (deterministic)
#   Phase 3 — sequential ledger append in sorted order
#
# Same inputs → byte-identical canonical result (excluding _instrumentation).
# _instrumentation holds wall-clock floats and is explicitly non-canonical.

def _generate_one(turn_index: int, spec: dict[str, Any]) -> dict[str, Any]:
    """
    Pure model generation for one turn. No ledger writes.
    Returns generation result + non-canonical timing data.
    Raises on model error — caller handles per-turn failure.
    """
    run_id = spec["run_id"]
    sender = spec["sender"]
    recipient = spec["recipient"]
    input_text = spec["input_text"]
    cfg = spec.get("model_config") or {}
    model_name = cfg.get("model_name", "stub")
    role = cfg.get("role", "proposal")

    prompt = _build_prompt(input_text)
    prompt_hash = _sha256(prompt)

    gen_start = time.monotonic()
    runner_payload = run_proposal(
        run_id=run_id,
        sender=sender,
        recipient=recipient,
        role=role,
        prompt=prompt,
        model_name=model_name,
    )
    gen_end = time.monotonic()

    return {
        "turn_index": turn_index,
        "run_id": run_id,
        "sender": sender,
        "recipient": recipient,
        "role": role,
        "model_name": model_name,
        "prompt_hash": prompt_hash,
        "runner_payload": runner_payload,
        "extra_metadata": spec.get("extra_metadata"),
        "_gen_start": gen_start,
        "_gen_end": gen_end,
    }


def _append_one_turn(
    turn_index: int,
    gen: dict[str, Any],
    ledger_path: Path,
) -> TurnExecutionResult:
    """Append one generated turn to the ledger. Sequential — no concurrent calls."""
    run_id = gen["run_id"]
    runner_payload = gen["runner_payload"]
    content = runner_payload["content"]
    output_hash = runner_payload["output_hash"]
    model_name = gen["model_name"]
    role = gen["role"]
    sender = gen["sender"]
    recipient = gen["recipient"]
    prompt_hash = gen["prompt_hash"]
    extra_metadata = gen.get("extra_metadata")

    append_start = time.monotonic()

    gate_dicts = [
        {
            "event_type": "model_call_record",
            "substrate_version": SUBSTRATE_VERSION,
            "run_id": run_id,
            "sender": sender,
            "recipient": recipient,
            "model_name": model_name,
            "prompt_hash": prompt_hash,
        },
        {
            "event_type": "model_output_record",
            "substrate_version": SUBSTRATE_VERSION,
            "run_id": run_id,
            "model_name": model_name,
            "output_hash": output_hash,
        },
        {
            "event_type": "routing_decision_record",
            "substrate_version": SUBSTRATE_VERSION,
            "run_id": run_id,
            "sender": sender,
            "recipient": recipient,
            "role": role,
        },
    ]

    created_at = _deterministic_created_at(run_id, content)
    provenance: dict[str, Any] = {
        "prompt_hash": prompt_hash,
        "model_name": model_name,
        "output_hash": output_hash,
        "substrate_version": SUBSTRATE_VERSION,
        "runner_output": runner_payload,
    }
    if extra_metadata:
        provenance["extra"] = extra_metadata

    event = make_transcript_event(
        run_id=run_id,
        sender=sender,
        recipient=recipient,
        role=role,
        content=content,
        created_at=created_at,
        metadata={"provenance": provenance},
    )

    with CognitiveTransaction(ledger_path) as txn:
        for g in gate_dicts:
            txn.stage_gate(g)
        validate_transcript_event(event)   # raises → ROLLBACK
        txn.stage_transcript(event)
    # COMMIT

    append_end = time.monotonic()

    return TurnExecutionResult(
        turn_index=turn_index,
        records=gate_dicts,
        transcript_messages=[event],
        instrumentation={
            "turn_index": turn_index,
            "generation_start": gen["_gen_start"],
            "generation_end": gen["_gen_end"],
            "append_start": append_start,
            "append_end": append_end,
        },
    )


def run_parallel_turns(
    turns: list[dict[str, Any]],
    ledger_path: str | Path,
    *,
    max_workers: int = 4,
) -> dict[str, Any]:
    """
    Execute model generation concurrently, append to ledger sequentially
    in deterministic turn-index order.

    Each turn spec must contain: input_text, run_id, sender, recipient.
    Optional: model_config, extra_metadata.

    Gate ordering per turn (enforced in Phase 3):
      model_call_record → model_output_record → routing_decision_record
      → transcript.message

    Failed turns are recorded in 'failed'; they produce no ledger writes.
    Ledger remains valid after partial failure.

    _instrumentation in return value contains wall-clock floats.
    It is explicitly non-canonical and must be excluded from canonical_json
    comparisons.
    """
    if not turns:
        raise ValueError("turns must be non-empty")

    ledger_path = Path(ledger_path)

    # ── Phase 1: Concurrent model generation ─────────────────────────────────
    generated: dict[int, dict[str, Any]] = {}
    errors: dict[int, str] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_generate_one, idx, spec): idx
            for idx, spec in enumerate(turns)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                generated[idx] = future.result()
            except Exception as exc:
                errors[idx] = str(exc)

    # ── Phase 2: Sort by turn index (deterministic append order) ──────────────
    ordered = sorted(generated.items())

    # ── Phase 3: Sequential append to ledger ──────────────────────────────────
    turn_results: list[TurnExecutionResult] = [
        _append_one_turn(idx, gen, ledger_path) for idx, gen in ordered
    ]

    transcript_events = replay_transcript_events(ledger_path)
    replay_audit = compute_replay_audit(transcript_events)
    chain_status = verify_mixed_ledger(ledger_path)

    return {
        "turns_requested": len(turns),
        "turns_completed": len(turn_results),
        "turns_failed": len(errors),
        "failed": {str(k): v for k, v in sorted(errors.items())},
        "results": turn_results,
        "event_count": len(transcript_events),
        "replay_audit": replay_audit,
        "chain_ok": chain_status.get("ok", False),
        "_instrumentation": [r.instrumentation for r in turn_results],
    }


# ── run_conversation (replay-only, no model calls) ─────────────────────────────

def run_conversation(
    ledger_path: str | Path,
    *,
    include_history: bool = True,
    max_history_events: int = DEFAULT_MAX_HISTORY_EVENTS,
) -> dict[str, Any]:
    """
    Derive current conversation state entirely from the ledger. No model calls.
    Safe to call repeatedly — always produces the same result for identical ledger.
    """
    events = replay_transcript_events(Path(ledger_path))

    result: dict[str, Any] = {
        "event_count": len(events),
        "latest_event": _safe_result_view(events[-1]) if events else None,
        "include_history": include_history,
    }

    # NON-AUTHORITATIVE replay-derived convenience context.
    # Deterministic and bounded only.
    # Must never become canonical cognition state.
    # Replay truth remains recorded transcript events.
    if include_history:
        result["history_summary"] = build_history_summary(events, max_history_events)

    return result
