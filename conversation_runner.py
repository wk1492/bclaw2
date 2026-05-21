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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ledger_writer import LedgerWriter
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
) -> list[dict[str, Any]]:
    """
    Bounded, deterministic summary of recent transcript events.

    - Derived solely from already-replayed transcript events (no I/O).
    - Ordered by topology linearization order from replay_transcript_events.
    - Bounded: at most max_events events (tail truncation).
    - Deterministic: identical input → identical output.
    - No randomness, no wall-clock time, no UUIDs introduced.
    - Prior events are never mutated.
    """
    if max_events < 1:
        raise ValueError("max_events must be at least 1")
    bounded = events[-max_events:] if len(events) > max_events else events
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

    # ── Gate record 1: ModelCallRecord ────────────────────────────────────────
    _append_gate_record(
        {
            "event_type": "model_call_record",
            "substrate_version": SUBSTRATE_VERSION,
            "run_id": run_id,
            "sender": sender,
            "recipient": recipient,
            "model_name": model_name,
            "prompt_hash": prompt_hash,
        },
        ledger_path,
    )

    # ── Model call ────────────────────────────────────────────────────────────
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

    # ── Gate record 2: ModelOutputRecord ──────────────────────────────────────
    _append_gate_record(
        {
            "event_type": "model_output_record",
            "substrate_version": SUBSTRATE_VERSION,
            "run_id": run_id,
            "model_name": model_name,
            "output_hash": output_hash,
        },
        ledger_path,
    )

    # ── Gate record 3: RoutingDecisionRecord ──────────────────────────────────
    _append_gate_record(
        {
            "event_type": "routing_decision_record",
            "substrate_version": SUBSTRATE_VERSION,
            "run_id": run_id,
            "sender": sender,
            "recipient": recipient,
            "role": role,
        },
        ledger_path,
    )

    # ── Build and append transcript event ─────────────────────────────────────
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

    validate_transcript_event(event)
    append_transcript_event(event, ledger_path)

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
