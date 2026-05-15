# Phase 1B: Deterministic Claim Lineage Tracing

**Status:** Planning stub — no implementation
**Depends on:** BCLAW2 freeze checkpoint (HEAD f13ef16)
**Allowed base:** `epistemic_graph.py`, `epistemic_graph_queries.py`, `epistemic_diff.py`

---

## 1. Scope

Phase 1B adds two pure read-only operations over already-built epistemic graphs:

1. **Transitive dependency traversal** — given a claim_id, walk the directed edge
   graph to collect all claims that the target claim transitively depends on
   (ancestors), and optionally all claims that transitively depend on it
   (descendants).

2. **Claim lineage trace** — given a claim_id, produce a deterministic ordered
   record of the chain of epistemic events that led to its current status, by
   following parent_claim_id and evidence_ref edges in topological order.

Both operations are pure functions over the output of `build_epistemic_graph`.
Neither writes to any ledger, alters any graph, or affects any replay path.

---

## 2. Intended Interfaces

```python
# Proposed signatures — not yet implemented

def get_ancestors(graph: dict, claim_id: str, depth: int | None = None) -> list[str]:
    """
    Return sorted list of claim_ids that claim_id transitively depends on.
    Follows directed edges source→target (source depends on target).
    depth=None means unbounded. depth=1 is equivalent to direct evidence_refs.
    Pure function. No mutation. Returns [] if claim_id not in graph.
    """

def get_descendants(graph: dict, claim_id: str, depth: int | None = None) -> list[str]:
    """
    Return sorted list of claim_ids that transitively depend on claim_id.
    Follows edges in reverse direction (target→source).
    Pure function. No mutation.
    """

def trace_claim_lineage(graph: dict, claim_id: str) -> dict:
    """
    Produce a deterministic lineage record for claim_id.

    Returns:
        {
            "claim_id":   str,
            "ancestors":  list[str],   # topological order, ancestors first
            "path_edges": list[dict],  # {"source": str, "target": str, "relation": str}
        }

    Pure function. Deterministic. No mutation. Raises ValueError if claim_id absent.
    """
```

---

## 3. Deterministic Invariants

All Phase 1B functions must satisfy:

- **Pure**: no I/O, no logging, no filesystem access, no global state mutation
- **Deterministic**: identical inputs produce identical outputs across all runs and
  PYTHONHASHSEED values
- **Sorted outputs**: all returned lists are sorted alphabetically by claim_id
  unless topological ordering is the specified output (in which case Kahn's
  algorithm with alphabetical tie-break applies, consistent with
  `topological_claim_order` in `epistemic_graph.py`)
- **Stable serialization**: `json.dumps(result, sort_keys=True, separators=(",",":"))` 
  must produce byte-identical output across repeated calls with identical inputs
- **No mutation**: input graph dict and its node/edge tuples are never modified

---

## 4. Observational Semantics

Phase 1B output is observational only:

- Lineage traces are read-only views — they do not write to ledger, alter graph
  structure, or influence orchestration decisions
- They may be passed to `diff_epistemic_state` (via `claim_status_snapshot`) to
  compare lineage snapshots across graph versions, but this is optional
- They are not authoritative state — they are derived views that can be
  recomputed deterministically from any graph at any time

---

## 5. Forbidden Escalations

Phase 1B must NOT:

- introduce recursive normalization of nested claim payloads
- add a generalized graph traversal framework beyond the two functions above
- couple lineage tracing to ledger append paths
- introduce async or concurrent traversal
- add caching or memoization that survives function return
- alter `build_epistemic_graph`, `validate_epistemic_graph`, `detect_cycles`,
  or `topological_claim_order`
- modify any substrate, ledger, replay, or topology module
- add new dependencies beyond the Python standard library

---

## 6. Allowed Files

When implementation begins, only these files may be created or modified:

- `epistemic_lineage.py` — new module, ≤ 80 lines
- `test_epistemic_lineage.py` — new test file, ≤ 120 lines

No other files may change. Diff budget at implementation: ≤ 200 lines total.

---

## 7. Implementation Preconditions

Before any Phase 1B implementation begins:

1. `./doctor.sh --strict` must pass
2. Full test suite must be green
3. HEAD must be at or descend from `f13ef16`
4. `docs/BCLAW2_FREEZE_CHECKPOINT.md` must be committed

These are hard preconditions, not suggestions.
