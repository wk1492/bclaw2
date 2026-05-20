# History Summary Boundary

## Authority boundary

`history_summary` is **convenience context only**.

Transcript events recorded in the ledger are the authoritative record of
what happened in any conversation. Nothing derived from those events —
including `history_summary` — replaces or overrides that record.

## What history_summary is

A bounded, deterministic, read-only slice of recently replayed transcript
events. It is produced by `build_history_summary()` in `conversation_runner.py`
and is intended to give a caller a quick view of recent context without
requiring them to process the full event log.

## What history_summary is not

- It is **not** a substitute for replay or audit.
- It is **not** a memory store.
- It is **not** authoritative about what agents said, decided, or concluded.
- It is **not** an input to the ledger or hash chain.
- It is **not** a canonical cognition state.

## Summaries are lossy compression

Truncation is applied: at most `max_events` (default 10) events are
included. Older events are dropped. A caller reading only `history_summary`
has an incomplete view of the conversation. For full fidelity, replay
directly from the ledger via `replay_transcript_events`.

## Summaries must never replace replay or audit

Any system that needs to verify what occurred must read the ledger directly.
`history_summary` is for display and convenience, not for governance,
arbitration, or audit decisions.

## Summaries are replay-derived, not runtime memory

`build_history_summary` accepts a list of already-replayed events.
It performs no I/O. It calls no models. It introduces no wall-clock time,
no random values, and no UUIDs. Identical input always produces identical
output.

## Determinism contract

- Event order: topology linearization order from `replay_transcript_events`.
  Never re-sorted, never shuffled.
- Truncation: tail (most recent N events). Deterministic for identical input.
- Field normalization: `_safe_result_view` strips ledger-internal hash fields
  and renames `timestamp` → `descriptive_timestamp` to prevent callers from
  treating the ledger append time as authoritative ordering.

## include_history=True must never create hidden mutable state

Enabling history inclusion only controls whether `history_summary` appears
in the return value of `run_conversation`. It does not write to any file,
does not mutate any event, and does not change ledger state.

## Summaries must remain deterministic across runs

Running `run_conversation` twice on the same ledger with the same parameters
must produce byte-identical `history_summary` output. Any change to summary
construction logic (max_events default, truncation strategy, field mapping)
constitutes a **boundary version change** and requires explicit review before
merging.

## Changing summary construction rules

If the construction rules change (new fields included, different truncation,
different ordering), the change must be:

1. Documented in this file with a new version note.
2. Reviewed against all callers of `build_history_summary`.
3. Tested with a determinism regression test for the new behavior.
4. Committed with an explicit note that the boundary semantics changed.

Silently changing summary construction is the primary drift risk this
boundary exists to prevent.
