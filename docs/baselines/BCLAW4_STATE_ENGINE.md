# BCLAW4 State Engine

Branch: bclaw4-chaos-lab-001
Experiment: 004
Date: 2026-05-15

## Design Principle

Transcript communication is computational substrate.
`reduce_transcript_state` is a pure, order-independent reducer that derives
canonical system state from a list of transcript events.
No side effects. No timestamps. No randomness.

## Derived State Fields

| Field | Type | Description |
|---|---|---|
| proposal_count | int | Events with role=="proposal" |
| critique_count | int | Events with role=="critique" |
| accepted_count | int | Critiques referenced by any arbiter |
| rejected_count | int | Proposals with at least one accepted critique |
| unresolved_count | int | Critiques not referenced by any arbiter |
| participants | list[str] | Sorted unique senders |
| last_status | str | Role of last event in linearized order |
| thread_ids | list[str] | Sorted message_ids of all comm events |
| transcript_hash | str | sha256(canonical(thread_ids)) |

## Snapshot Event

Appended as role="system" with content:
`canonical_json({"marker":"transcript.state_snapshot","state_version":1,"derived_state":{...}})`

## Determinism Guarantees

- Deduplicates by message_id (first wins) before reducing
- All derived fields are set-based or aggregate-only (order-independent)
- transcript_hash = sha256(canonical(sorted message_ids))
- summary_id excludes ledger_path and LedgerWriter decoration timestamps
