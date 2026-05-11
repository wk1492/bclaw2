# Transcript Replay Artifact Baseline

Source commit: e9b3bf4
Baseline doc commit: 980cf81

## Artifact

`artifacts/baselines/transcript_replay_e9b3bf4.json`

Contains the canonical deterministic output of the proposal → critique → arbiter transcript exchange, generated from `transcript_event.py` and `transcript_validator.py` at commit `e9b3bf4`.

## Exchange summary

- `tmsg_1085c8a9011f08b126ce680e` — proposal (agent_a → agent_b)
- `tmsg_6c9039f0b478ad058cfae721` — critique (agent_b → agent_a, references proposal)
- `tmsg_6f1a1a0f8671d0d62a3cb98e` — arbiter (agent_arbiter → broadcast, references critique + proposal)

## Expected replay invariants

- Replay order is always: proposal → critique → arbiter
- Parent relationships are fixed and content-addressed
- message_ids are deterministic (SHA-256 of event content, no randomness)
- Canonical serialization: sort_keys=True, separators=(",", ":"), ensure_ascii=False
- Reconstruction is stable regardless of append order

## Regression truth

Byte-stable replay output from this exchange is the regression truth for all future transcript, arbitration, FCM, and message-bus work. Any change that alters message_ids, parent relationships, reconstruction ordering, or canonical serialization output must be treated as an intentional migration and documented against this baseline.
