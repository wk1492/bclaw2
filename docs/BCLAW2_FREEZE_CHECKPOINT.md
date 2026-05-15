# BCLAW2 Freeze Checkpoint

**Date:** 2026-05-14
**Freeze HEAD:** f13ef16
**Branch:** main
**Tests passing:** 545
**Worktree at freeze:** clean
**Doctor strict:** PASS

---

## 1. Purpose

This document records the state of the BCLAW2 deterministic cognition substrate at
the Phase 1C epistemic graph query + diff integration freeze. It is a read-only
audit artifact. Nothing here alters ledger semantics, hash chains, replay behavior,
or baseline artifacts.

---

## 2. Canonical Commit Sequence

```
f13ef16 Add deterministic epistemic_diff with graph snapshot integration
0aaba72 Add static topology contract
1fd8a10 Add deterministic epistemic graph query helpers
f1ea6f0 Add deterministic epistemic graph topology layer
83dd0dd Add derived epistemic graph view
9881dfd Add epistemic event schema extension
fa72d2c Add transcript replay from ledger only proof
94978df Add replay-from-ledger-only reconstruction proof
63d3623 Add canonical serialization stability audit
c81d0f2 Add transcript topology baseline enforcement
0fb37f9 Add transcript topology replay summary baseline
c38284a Document lineage drift failure mode
66a1902 Add strict doctor workflow precondition
c764330 Add runner validation to doctor
3f9691a Add runner transcript capture proof
b52e57a Add deterministic model runner abstraction
53bc90e Add BCLAW2 stable checkpoint baseline
c8d4653 Add full stack substrate smoke test
c6b370a Add substrate atomicity crash detection tests
ddc0846 Add compatibility guarantees to substrate contract
fe86c25 Add formal substrate error taxonomy and contract
23cd4a6 Add frozen provenance audit fixtures
```

---

## 3. Deterministic Replay Guarantees

The following properties hold at this freeze and must be preserved by all future
layers:

**3.1 Canonical serialization**
All content-addressed IDs and hash inputs use:
```python
json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```
This is the single canonical form. It is never varied, never parameterized, never
extended with new sort options.

**3.2 Content-addressed IDs**
- `tmsg_` — transcript message IDs: sha256 of canonical event payload
- `tlin_` — linearization IDs: sha256 of canonical ordered message-ID list
- `tdiff_` — transcript diff IDs: sha256 of canonical diff payload
- `topo_` — topology artifact IDs: sha256 of canonical topology summary
- `claim_` — epistemic claim IDs: sha256 of canonical event payload minus decoration fields

No random, UUID, or wall-clock component appears in any content-addressed ID.

**3.3 Input-order independence**
`build_epistemic_graph` and `compute_transcript_linearization` produce identical
output regardless of the order in which events are supplied. This is enforced by
`test_node_sort_is_deterministic` and `test_topological_order_is_deterministic`.

**3.4 Replay-from-ledger-only reconstruction**
Given a JSONL ledger file and no in-memory event objects, `replay_transcript_events`
reconstructs byte-identical topology hashes and message-ID sequences.
Proven by `test_graph_reconstruction_from_ledger_only` and
`test_topology_hash_consistent_from_mixed_ledger`.

**3.5 PYTHONHASHSEED independence**
Canonical serialization output is byte-identical across all `PYTHONHASHSEED` values.
Enforced by `test_canonical_serialization_stability.py` (subprocess test across 5
seeds).

---

## 4. Provenance Hash Stability

The following baseline hash is frozen. Any change to serialization, ordering, or
field structure that alters this value is a substrate contract violation:

**Frozen topology hash:**
```
b4aaf688694fd4b055371d8d238bb0c8386d397e39ed009533dd935438d4ad4c
```

**Source artifact:**
`artifacts/baselines/transcript_topology_replay_summary_c38284a.json`

**Role sequence encoded:** `[proposal, critique, critique, arbiter]`
**Linearized order (4 events):** as recorded in the artifact above.

This hash is enforced at every test run by
`test_transcript_topology_replay_summary_baseline.py`.

---

## 5. Topology Cycle Safety

`detect_cycles` uses iterative DFS (no recursion depth limit). `topological_claim_order`
raises `ValueError` on cycle detection before producing any output.
`validate_epistemic_graph` reports self-references and dangling edge endpoints as
discrete errors.

No epistemic graph operation silently proceeds on a cyclic or structurally invalid
graph. No cycle suppression path exists.

---

## 6. Doctor Strict Enforcement Role

`doctor.sh --strict` enforces workspace identity as a substrate precondition:
- repo root must be `~/Downloads/bclaw2`
- current branch must be `main`
- worktree must be clean (no uncommitted changes)
- five required substrate files must be present:
  `transcript_event.py`, `transcript_ledger.py`, `transcript_topology.py`,
  `model_runner.py`, `SUBSTRATE_CONTRACT.md`

Doctor strict is required before any mutation, schema change, orchestration change,
runner/transcript wiring, or FCM/graph work. Failure is a hard stop.

The failure mode it guards against — coherent-output-on-wrong-lineage — is defined
in `SUBSTRATE_CONTRACT.md` Section 7. Code that is internally coherent but produced
from the wrong repo or branch cannot be reconciled with frozen baseline artifacts
without re-deriving all hashes.

---

## 7. Absence of Autonomous Mutation Paths

At this freeze, no code path writes to a ledger, the filesystem, or any external
state without an explicit caller-supplied path. There is no:
- background writer thread
- daemon process
- auto-flush mechanism
- scheduled mutation
- implicit side-effecting import

All persistence is explicit. All replay is pull-based. All diff computation is pure.

---

## 8. Clean-Room Reconstruction Guarantee

Given only the JSONL ledger file and the module source at this HEAD, any agent can
reconstruct:
- the full topology hash
- the linearized message order
- the epistemic graph (nodes, edges, dangling refs)
- the claim status snapshot
- the epistemic diff between any two graph states

without access to any runtime state, in-memory cache, or external service.
This guarantee is tested by the replay-from-ledger-only proof suite
(`test_replay_from_ledger_only.py`, `test_transcript_replay_from_ledger_only.py`,
`test_epistemic_graph.py::test_graph_reconstruction_from_ledger_only`).

---

## 9. Layer Inventory at Freeze

### Substrate core
| Module | Role |
|---|---|
| `transcript_event.py` | Schema, canonical JSON, content-addressed message IDs |
| `transcript_ledger.py` | Append, replay, filter, topology, mixed-ledger verification |
| `transcript_validator.py` | Field and structural validation |
| `transcript_topology.py` | Kahn's linearization, cycle detection, topology hash |
| `transcript_diff.py` | Set-based transcript diff, content-addressed diff_id |
| `ledger_writer.py` | Hash-chain append, LedgerWriter, verify_ledger |
| `substrate_errors.py` | Stable error code taxonomy (SUBSTRATE_VERSION 1) |
| `substrate_contract.py` | Contract enforcement wrapper |

### Runner
| Module | Role |
|---|---|
| `model_runner.py` | Deterministic stub runner, all-string payload, no timestamps |

### Epistemic extension (BCLAW3 Phase 1, complete at freeze)
| Module | Role |
|---|---|
| `epistemic_event.py` | Epistemic field schema, claim IDs, strip helper |
| `epistemic_graph.py` | EpistemicNode/EpistemicEdge, build/validate/detect_cycles/topological |
| `epistemic_graph_queries.py` | Pure query helpers + claim_status_snapshot |
| `epistemic_diff.py` | Deterministic shallow diff of epistemic state dicts |
| `topology_contract.py` | Static workflow expectation derivation from topology docs |

### Frozen baseline artifacts
| Artifact | Role |
|---|---|
| `artifacts/baselines/golden_replay_audit.json` | Golden replay audit fixture |
| `artifacts/baselines/provenance_fixtures.json` | Provenance audit fixture |
| `artifacts/baselines/transcript_topology_replay_summary_c38284a.json` | Frozen topology hash |

---

## 10. Known Stale Artifacts

| File | Issue |
|---|---|
| `verify_substrate.sh` | Stage 2 expected count hardcoded at 323; actual is 545. Fails on count check. Do not use as gate. |
| `docs/PROJECT_UPDATE_TRANSCRIPT_SUBSTRATE.md` | References HEAD `6ee8979` and 323 tests. Historical only; superseded by this document. |

---

## 11. Next Layer: Phase 1B Scope

Defined separately in `docs/PHASE1B_LINEAGE_PLAN.md`.

Phase 1B is narrowly scoped to deterministic transitive dependency traversal and
claim lineage tracing over already-built epistemic graphs. It does not alter any
substrate, replay, ledger, or topology module.
