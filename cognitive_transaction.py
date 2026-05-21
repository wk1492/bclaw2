"""
cognitive_transaction.py — SUBSTRATE_VERSION=1

Commit-or-rollback semantics for cognitive operations.

A cognitive operation either commits canonically or never existed historically.

    BEGIN COGNITIVE TRANSACTION
        speculative generation
        validation / audit gates
        provenance construction
    COMMIT CANONICAL EVENTS

    or:

    ROLLBACK ENTIRE OPERATION

Nothing is written to the ledger until the transaction commits. Any exception
during the transaction causes complete rollback — the ledger is byte-identical
to its state before the transaction began.

This enforces:
    speculative generation → validation → deterministic commit

not:
    speculative generation → partial ledger writes → cleanup

Thread safety: CognitiveTransaction is NOT thread-safe. Each concurrent turn
must use its own instance. Commit must execute under the caller's sequential
write discipline (e.g., run_parallel_turns Phase 3).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ledger_writer import LedgerWriter
from transcript_ledger import append_transcript_event

_GATE = "gate"
_TRANSCRIPT = "transcript"


class CognitiveTransaction:
    """
    Context manager for atomic cognitive commit semantics.

    Usage:
        with CognitiveTransaction(ledger_path) as txn:
            txn.stage_gate(model_call_record)
            result = run_proposal(...)          # speculative
            txn.stage_gate(model_output_record)
            txn.stage_gate(routing_decision_record)
            event = make_transcript_event(...)
            validate_transcript_event(event)    # raises → ROLLBACK
            txn.stage_transcript(event)
        # COMMIT: all staged records written in order, hash chain intact

    On any exception inside the with-block, __exit__ discards all staged
    records and re-raises. The ledger is not touched.
    """

    def __init__(self, ledger_path: str | Path) -> None:
        self._path = Path(ledger_path)
        self._staged: list[tuple[str, dict[str, Any]]] = []

    # ── staging ───────────────────────────────────────────────────────────────

    def stage_gate(self, record: dict[str, Any]) -> None:
        """Stage one gate record. Not written until commit."""
        self._staged.append((_GATE, dict(record)))

    def stage_transcript(self, event: dict[str, Any]) -> None:
        """Stage one transcript event. Not written until commit."""
        self._staged.append((_TRANSCRIPT, dict(event)))

    @property
    def staged_count(self) -> int:
        """Number of records staged for this transaction."""
        return len(self._staged)

    # ── context manager ───────────────────────────────────────────────────────

    def __enter__(self) -> CognitiveTransaction:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            self._staged.clear()
            return False  # ROLLBACK — re-raise
        self._commit()
        return False  # COMMIT — normal exit

    def _commit(self) -> None:
        """Write all staged records to the ledger in staged order."""
        for kind, record in self._staged:
            if kind == _GATE:
                LedgerWriter(self._path).append(record)
            else:
                append_transcript_event(record, self._path)
