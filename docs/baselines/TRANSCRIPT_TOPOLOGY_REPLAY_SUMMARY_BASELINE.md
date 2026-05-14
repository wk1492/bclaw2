# Transcript Topology Replay Summary Baseline

**HEAD:** c38284a — Document lineage drift failure mode
**Date:** 2026-05-13
**Tests:** 383 passed, 0 failed
**Artifact:** `artifacts/baselines/transcript_topology_replay_summary_c38284a.json`

---

## Canonical Sample

Exchange: proposal → two critiques → arbiter (4 events, 0 orphaned)

| Position | Role | message_id | Sender |
|---|---|---|---|
| 0 | proposal | `tmsg_23d02560914150e2f977be09` | agent_proposer |
| 1 | critique | `tmsg_72dd9c291abf9060c6cb8842` | agent_critic_a |
| 2 | critique | `tmsg_64436892b8fddc273e37725d` | agent_critic_b |
| 3 | arbiter | `tmsg_60cbf9b92932b12e8669b51a` | agent_arbiter |

---

## Frozen Topology Values

| Field | Value |
|---|---|
| `topology_hash` | `b4aaf688694fd4b055371d8d238bb0c8386d397e39ed009533dd935438d4ad4c` |
| `linearization_id` | `tlin_9612e4b6a709b298675134f6` |
| `event_count` | 4 |
| `orphaned` | `[]` |

---

## Invariants

- **Shuffled input must produce identical `topology_hash` and `linearized_order`.** The linearization algorithm (`linearize_transcript_topology`) sorts by `(created_at, message_id)` and is input-order independent.
- `topology_hash` is sha256 of `canonical(linearized_order)` — it encodes the full dependency resolution, not just the event set.
- `orphaned` is empty: all parent/reference links resolve within this event set.
- These hashes are stable across Python versions and process restarts provided canonical serialization (`sort_keys=True, separators=(",", ":"), ensure_ascii=False`) is unchanged.

---

## Source Functions

| Function | Module |
|---|---|
| `run_transcript_critique_loop` | `transcript_critique_loop.py` |
| `replay_transcript_events` | `transcript_ledger.py` |
| `replay_transcript_topology` | `transcript_ledger.py` |
| `compute_transcript_linearization` | `transcript_topology.py` |

---

## Version Gate

Any change that alters `topology_hash` or `linearized_order` for this canonical sample requires a new baseline artifact and a new `SUBSTRATE_VERSION`.
