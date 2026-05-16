# Deterministic Agent Session Protocol

## Purpose

`TASK_28_DETERMINISTIC_AGENT_SESSION_PROTOCOL` defines a bounded protocol for multi-step LLM-to-LLM coordination over transcript-native communication. It is documentation, template, and lightweight test coverage only. It does not introduce runtime enforcement, scheduling, daemon behavior, model calls, ledger mutation, replay mutation, or autonomous execution.

## 1. Session Definition

An agent session is a bounded, replay-addressable coordination window. A valid session is:

- **bounded**: it declares `session_id`, `max_moves`, participating agents, objective, allowed files, forbidden files, invariant attestations, and stop conditions before work proceeds.
- **explicit**: scope, authority, participants, and file boundaries are written into a session packet rather than inferred from chat history.
- **non-autonomous by default**: the protocol describes coordination rules only; it does not authorize schedulers, daemons, background loops, live model calls, or unbounded continuation.
- **transcript-native**: moves consume and emit transcript message IDs, not hidden state.
- **replay-auditable**: each move records context hashes, consumed messages, produced messages, file changes, tests, invariants, drift state, and unresolved items.
- **final-report-attested**: session completion requires a report that names tests, files changed, drift risks, unresolved items, and authority-boundary status.

Minimum session packet fields include:

- `session_id`
- `max_moves`
- `participants`
- `active_objective`
- `allowed_files`
- `forbidden_files`
- `invariant_attestations_required`
- `stop_conditions`

## 2. Move Semantics

A move is one bounded contribution by one participant within the active session. Every move must declare:

- `move_number`
- `acting_agent`
- `input_context_hash`
- `transcript_message_ids_consumed`
- `output_transcript_message_ids`
- `files_changed`
- `tests_run`
- `invariant_attestations`
- `drift_status`
- `unresolved_items`

Moves must be replay-addressable by their declared transcript inputs and outputs. A move may propose, critique, test, document, or report. A move may not silently alter the session objective, expand file scope, mutate replay truth, or create hidden state that is required for future interpretation.

`drift_status` must be one of:

- `IN_SCOPE`
- `DRIFT_RISK`
- `BLOCKED_PENDING_HUMAN_APPROVAL`

`DRIFT_RISK` is required whenever a move proposes scope expansion, touches unclear authority boundaries, or identifies an ambiguity that could change replay, ledger, or runtime meaning.

## 3. Ten-Move Rule

After every 10 moves, the active session must stop and emit a ten-move report before any continuation. The report must summarize:

- progress toward the active objective
- tests run and their results
- commits or uncommitted changes
- drift risks
- unresolved items
- recommended next moves

The ten-move report requirement applies even when work appears successful. Continuing after a ten-move boundary requires a new explicit scoped continuation or a fresh session packet.

## 4. `1` Command Rule

A standalone `1` means: continue the active scoped task or session only if one exists.

If no active scoped task or session exists, the response must be exactly:

```text
NO_ACTIVE_TASK
```

The `1` command does not create a new session, expand authority, approve destructive actions, or waive invariant attestations.

## 5. Drift Control

GPT acts as the drift monitor and protocol keeper for this protocol. That role means GPT must preserve the declared objective, file boundaries, authority boundaries, and invariant requirements unless a drift risk is explicitly recorded.

Drift-control rules:

- Scope expansion requires `DRIFT_RISK`.
- Destructive, ambiguous, or permission-sensitive actions require human approval before execution.
- No silent invariant drift is allowed.
- Unresolved ambiguity must be recorded in `unresolved_items` rather than treated as permission.
- File changes outside `allowed_files` are forbidden unless a human explicitly rescopes the session.
- Runtime, ledger, replay, adapter, router, ingestion, arbitration, branch replay, baseline, CI, scheduler, daemon, and autonomy changes are out of scope for this documentation-only protocol.

## 6. Authority Boundaries

The session protocol may coordinate:

- proposals
- critiques
- tests
- documentation
- read-only analysis

The session protocol may not:

- bypass ingestion
- mutate ledger outside an approved path
- regenerate replay truth
- auto-merge branches
- silently promote counterfactuals
- call live models during replay
- self-edit without scoped permission
- introduce runtime enforcement
- introduce a scheduler or daemon
- authorize autonomous execution

A session packet or report is an audit artifact. It is not a runtime permission grant.

## 7. Required Templates

Two templates define the minimum transcript-native artifacts for this protocol:

- `docs/templates/agent_session_packet_template.json`
- `docs/templates/agent_session_report_template.md`

The packet template captures the session boundary and per-move declaration shape. The report template captures the required ten-move and final-report attestations.

## 8. Tests

Lightweight documentation tests verify that the protocol and templates contain the required fields and rules:

- `max_moves`
- `move_number`
- `acting_agent`
- `input_context_hash`
- `transcript_message_ids_consumed`
- `invariant_attestations`
- `drift_status`
- `unresolved_items`
- `NO_ACTIVE_TASK`
- ten-move report requirement

These tests are documentation guards only. They do not implement runtime enforcement.
