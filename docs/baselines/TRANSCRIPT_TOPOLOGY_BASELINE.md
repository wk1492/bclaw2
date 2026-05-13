# Transcript Topology Baseline

**Status:** frozen reference contract
**Date:** 2026-05-12
**Commit:** 1a71aff (tagged as 9f3c2a1 in request; actual HEAD at freeze)
**Artifact:** `artifacts/baselines/transcript_topology_9f3c2a1.json`
**Tests passing at freeze:** 304

---

## 1. Scope

This document freezes the deterministic transcript topology linearization contract
implemented in `transcript_topology.py`. All future changes to topology ordering,
dependency resolution, or ID generation must either preserve this contract exactly
or declare an explicit versioned migration.

No code behavior changes, replay/ledger/schema, or FCM modifications are part of
this baseline.

---

## 2. Public API

### `linearize_transcript_topology(events: list) -> list`

Returns events in deterministic topological order. No content-addressed ID.
Used internally by `compute_transcript_linearization` and `replay_audit.py`.

### `compute_transcript_linearization(events: list) -> dict`

Pure-functional, content-addressed linearization report. No file I/O.
Raises `TranscriptLinearizationError` on dependency cycles.

**Return schema:**

```
{
  "order":            list[str]   — message_ids in deterministic linearized order
  "node_count":       int         — total transcript events in input
  "orphaned":         list[str]   — sorted message_ids whose parent is not in the event set
  "topology_hash":    str         — sha256 of canonical(order)
  "linearization_id": str         — "tlin_" + sha256[:24] of canonical({order, orphaned})
}
```

### `TranscriptLinearizationError(ValueError)`

Raised when a dependency cycle is detected among the input events.

---

## 3. Ordering Rules

1. Root nodes (no `parent_message_id`, or parent not in event set) are emitted first.
2. A child node is not emitted until its `parent_message_id` has been emitted.
3. A referencing node is not emitted until all its `references` entries have been emitted.
4. Among nodes that are simultaneously ready, tie-break is `(created_at, message_id)` ascending — lexicographic on both fields.
5. Disconnected or orphaned nodes participate in the same tie-break with no additional penalty.

---

## 4. Canonical Sample: Four-Node Proposal → Critique × 2 → Arbiter

### Input (key fields only)

```
run_id: "run_topology_baseline"

proposal    message_id: tmsg_151bf84873cafa2ad5e43580
            role: proposal, sender: agent_a
            created_at: 2026-05-10T10:00:00+00:00
            parent: null, references: []

critique_a  message_id: tmsg_bed4d6b29a8d2b5c7f46d272
            role: critique, sender: agent_b
            created_at: 2026-05-10T10:00:01+00:00
            parent: tmsg_151bf84873cafa2ad5e43580
            references: [tmsg_151bf84873cafa2ad5e43580]

critique_b  message_id: tmsg_66345857a1ef78fab1d08e45
            role: critique, sender: agent_c
            created_at: 2026-05-10T10:00:02+00:00
            parent: tmsg_151bf84873cafa2ad5e43580
            references: [tmsg_151bf84873cafa2ad5e43580]

arbiter     message_id: tmsg_b8c21cd544d1e224358c108e
            role: arbiter, sender: agent_arbiter
            created_at: 2026-05-10T10:00:03+00:00
            parent: tmsg_bed4d6b29a8d2b5c7f46d272
            references: [tmsg_bed4d6b29a8d2b5c7f46d272,
                         tmsg_66345857a1ef78fab1d08e45,
                         tmsg_151bf84873cafa2ad5e43580]
```

### Output (frozen)

```json
{
  "linearization_id": "tlin_65647772b3b54c17b1671c53",
  "node_count": 4,
  "order": [
    "tmsg_151bf84873cafa2ad5e43580",
    "tmsg_bed4d6b29a8d2b5c7f46d272",
    "tmsg_66345857a1ef78fab1d08e45",
    "tmsg_b8c21cd544d1e224358c108e"
  ],
  "orphaned": [],
  "topology_hash": "f7b18c45403f802a5017d7d331e6211a586fa0774046e31a072aada20f4cf31a"
}
```

**Role sequence:** `["proposal", "critique", "critique", "arbiter"]`

Any implementation change that produces a different `topology_hash` or `linearization_id`
for this input is a breaking change.

---

## 5. Preserved Invariants

| Invariant | Guarantee |
|---|---|
| Insertion-order independence | All permutations of the same event set produce identical `order` |
| `PYTHONHASHSEED` independence | `sort_keys=True` in canonical JSON eliminates dict-iteration dependence |
| Byte-stability | Repeated calls to `compute_transcript_linearization` on the same input are byte-identical |
| Parent-before-child | For every event with `parent_message_id` in the event set, parent appears before child in `order` |
| Reference-before-referencing | For every `ref` in `event.references` that is in the event set, `ref` appears before the event in `order` |
| Sibling tie-break | Siblings (same-parent events simultaneously ready) sorted by `(created_at, message_id)` ascending |
| Cycle detection | Any dependency cycle raises `TranscriptLinearizationError`; no partial state is emitted |
| Orphan reporting | Events whose `parent_message_id` is not in the input set appear in `orphaned`, sorted |
| No side effects | `compute_transcript_linearization` does not write to ledger, file system, or any external state |

---

## 6. Canonical Serialization

All content-addressed IDs use:

```python
json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

- `sort_keys=True`: alphabetical key order, not insertion order
- `separators=(",", ":")`: no spaces after `,` or `:`
- `ensure_ascii=False`: unicode passes through unescaped

### ID prefix table

| Object | Prefix | Hash source |
|---|---|---|
| Linearization report | `tlin_` | `canonical({"order": order, "orphaned": orphaned})` |
| Topology hash | (raw sha256) | `canonical(order)` |

All IDs use the first 24 hex characters of the SHA-256 digest.

---

## 7. Failure Semantics

`TranscriptLinearizationError` (subclass of `ValueError`) is raised when Kahn's
algorithm exhausts all ready nodes while nodes remain — which is the exact condition
for a dependency cycle. The error message identifies the count and sorted IDs of the
remaining cyclic nodes. No partial output is returned.

---

## 8. Scope of This Baseline

This baseline covers only `transcript_topology.py`. It does not govern:

- `transcript_ledger.py` `replay_transcript_topology` (reads from a ledger path; separate I/O layer)
- `replay_audit.py` `compute_replay_audit` (multi-hash audit over the full event set)
- `transcript_diff.py` (set-based diff between event sets; separate contract)
- FCM dynamics, graph apply, or multi-step semantics (governed by `FCM_RUNTIME_SEMANTICS_v0.1.md`)
