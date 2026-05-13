# BCLAW2 Stable Checkpoint Baseline

**HEAD:** c8d4653 — Add full stack substrate smoke test
**Date:** 2026-05-13
**Tests:** 359 passed, 0 failed
**Working tree:** clean and pushed to origin/main

---

## Completed Layers

| Layer | Status |
|---|---|
| Transcript schema + validator | frozen |
| Hash-chained append-only ledger | frozen |
| Mixed replay + topology linearization | frozen |
| Deterministic agent handoff + critique loops | frozen |
| Provenance fixtures + substrate v1 error taxonomy | frozen |
| Crash-detection tests | frozen |
| Full-stack smoke test | frozen |

---

## Preserved Invariants

- Hash-chain semantics unchanged (`event_hash`, `rolling_hash`, `previous_hash` derivation)
- Canonical serialization unchanged (`json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`)
- Execution replay unchanged — transcript and execution events remain independent filter paths
- Baseline artifacts unchanged unless explicitly added with `git add -f`
- Transcript events remain data-only — no side effects, no model calls, no FCM mutation

---

## Substrate Contract

**SUBSTRATE_VERSION:** 1
**Module:** `substrate_errors.py`, `substrate_contract.py`
**Contract doc:** `SUBSTRATE_CONTRACT.md`

Error codes frozen at this checkpoint:

| Code | Trigger |
|---|---|
| `E_DUPLICATE_MESSAGE_ID` | Duplicate `message_id` on append |
| `E_MISSING_PARENT` | `parent_message_id` not in ledger |
| `E_PREVIOUS_HASH_MISMATCH` | Hash chain broken |
| `E_INVALID_JSON` | Truncated or corrupt ledger line |
| `E_MISSING_FINAL_NEWLINE` | File does not end with LF |

---

## Frozen Baseline Artifacts

| File | Purpose |
|---|---|
| `artifacts/baselines/transcript_topology_9f3c2a1.json` | Topology linearization baseline |
| `artifacts/baselines/provenance_fixtures.json` | Provenance audit fixture hashes |

Frozen topology hash: `f7b18c45403f802a5017d7d331e6211a586fa0774046e31a072aada20f4cf31a`

Frozen provenance hashes:
- `clean_chain`: `0b0eb7603d3c53b6940c1bef59bbf9fe845a0ce50faf8866d94311a79ecedfb8`
- `orphaned_critique`: `de676a53f5092e20546c997683d04620d9fe03b5b993bd50736131477acab25d`
- `broken_references`: `8365b304f600c4b82928bc26bd1dda9a6dacf38f9f0b2805b35b7ba85e6b677f`

---

## Next Version Requirements

A new checkpoint is required before merging any change that:
- alters canonical JSON serialization
- changes the hash algorithm
- changes line termination requirements
- modifies `SUBSTRATE_VERSION`
- mutates a frozen baseline artifact
- changes replay ordering semantics
