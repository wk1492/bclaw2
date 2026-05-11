# Transcript Message Bus Baseline

Current HEAD: e9b3bf4
Test count: 161 passed, 0 failed

## Phase commits

- `ecfb0b5` — transcript event schema + validator
- `95b65a2` — ledger append integration
- `e9b3bf4` — deterministic replay proof

## New transcript files

- `transcript_event.py` — schema, canonical serialization, content-addressed message_id
- `transcript_validator.py` — field validation, role enforcement, thread reconstruction
- `transcript_ledger.py` — validated append via LedgerWriter, replay/filter helpers
- `test_transcript_validator.py` — schema validation and serialization tests
- `test_transcript_ledger.py` — ledger append, mixed ledger, hash-chain tests
- `test_transcript_replay_proof.py` — end-to-end deterministic replay proof (proposal → critique → arbiter)

## Preserved invariants

- Hash-chain semantics: unchanged — transcript events flow through LedgerWriter unmodified
- Canonical serialization: unchanged — sort_keys=True, separators=(",", ":") enforced throughout
- Execution replay semantics: unchanged — transcript events are filtered out of execution replay
- Baseline artifacts: unchanged — no existing files modified across all three phases
- Transcript events: data-only — no agents, orchestration, UI, MCP, or domain heuristics introduced

## Regression promise

Future critique, arbitration, agent, FCM, or message-bus work must preserve deterministic transcript replay behavior as demonstrated in `test_transcript_replay_proof.py`. Any change that alters hash-chain semantics, replay output, or reconstruction ordering must be treated as an intentional migration and documented against this baseline.
