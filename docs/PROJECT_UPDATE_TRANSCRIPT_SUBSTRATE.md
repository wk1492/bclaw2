# Project Update: Deterministic Transcript Substrate Complete

**Date:** 2026-05-13
**HEAD:** 6ee8979
**Tests passing:** 323

---

## Milestone Summary

The deterministic transcript substrate layer is complete. Transcript events are now
the canonical conversation medium between agents. Graph and FCM layers are derived
views computed over the transcript, not the reverse.

---

## What Is Complete

| Component | Module(s) |
|---|---|
| Transcript schema and validation | `transcript_event.py`, `transcript_validator.py` |
| Append-only hash-chained ledger integration | `ledger_writer.py`, `transcript_ledger.py` |
| Mixed execution/transcript replay | `replay_execution_events`, `replay_transcript_events` |
| Topology linearization | `transcript_topology.py` — Kahn's algorithm, cycle detection, content-addressed `linearization_id` |
| Transcript diffing | `transcript_diff.py` — set-based, content-addressed `diff_id` |
| Critique loops | `transcript_critique_loop.py` |
| Deterministic agent handoff | `transcript_llm_agent.py` — fake model, two-agent exchange, ledger-mediated |
| Multi-step FCM preview and apply | `fcm_dynamics_preview.py`, `fcm_multi_step.py`, `fcm_graph_apply.py` |
| Golden replay audit fixtures | `artifacts/baselines/golden_replay_audit.json`, `replay_audit.py` |
| Provenance audit fixtures and baseline | `artifacts/baselines/provenance_fixtures.json`, `test_provenance_fixtures.py` |
| Topology baseline | `artifacts/baselines/transcript_topology_9f3c2a1.json`, `docs/baselines/TRANSCRIPT_TOPOLOGY_BASELINE.md` |

---

## Preserved Invariants

These properties hold across all current tests and must be maintained by future layers:

- **Deterministic replay** — given the same ledger, replay produces byte-identical output regardless of execution order or platform dict ordering
- **Content-addressed IDs and hashes** — all message IDs (`tmsg_`), topology IDs (`tlin_`), diff IDs (`tdiff_`), and audit hashes are derived from `sha256(canonical_json(payload))`; no random or time-based components
- **No runtime nondeterminism** — no `uuid4`, no `random`, no wall-clock timestamps in content-addressed paths
- **No model calls in core** — all deterministic behavior is exercised by a fake model; no external API dependencies
- **No autonomous mutation** — no code path writes to ledger, file system, or external state without an explicit caller-supplied path
- **Ledger semantics unchanged** — the hash-chain append contract (`LedgerWriter`, `verify_ledger`) is stable; existing ledger files remain valid
- **Replay semantics unchanged** — `replay_transcript_events` and `replay_execution_events` filter by `event_type`; adding new event types does not alter existing replay output

---

## Architecture Note

Transcript events (`event_type: "transcript.message"`) are the single source of truth
for agent communication. The topology layer (`linearize_transcript_topology`,
`compute_transcript_linearization`) and audit layer (`compute_replay_audit`) are
pure functions that read from the event set without writing back to it. The FCM
graph and dynamics layers consume the same applied-graph contract independently of
the transcript layer; they share only the canonical JSON serialization convention.

---

## Status

This is a research prototype. It is not production software. The fake model,
frozen timestamps, and deterministic IDs are deliberate design choices for
auditability, not limitations to be removed. No claims are made about autonomous
reasoning capability.
