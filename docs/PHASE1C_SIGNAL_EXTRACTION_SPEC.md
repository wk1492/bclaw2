# Phase 1C: Deterministic Signal Extraction for SSRE

**Status:** Design specification — no implementation
**Depends on:** BCLAW2 freeze checkpoint (HEAD f13ef16), Phase 1B lineage plan
**Base substrate:** `epistemic_graph.py`, `epistemic_graph_queries.py`,
`epistemic_diff.py`, `transcript_topology.py`, `transcript_ledger.py`

---

## 1. Objective

Define how the Self-Supervised Replay Evaluator (SSRE) extracts deterministic,
replay-safe signals from frozen replay artifacts. Signals are read-only observational
measurements derived from committed ledger content. They are not authoritative state,
do not alter control flow, and cannot modify any artifact they read.

The signal extraction layer sits between frozen artifacts and the rubric evaluation
layer. It produces labeled, provenance-traced, JSON-safe signal records that are
fully reproducible given the same input artifacts.

---

## 2. Architectural Invariants

The following invariants govern all signal extraction and must never be violated:

**2.1 Frozen-artifact-only operation**
Signals are derived exclusively from replay artifacts that exist in committed ledger
state. No signal extraction reads runtime state, in-memory caches, or external
services.

**2.2 Deterministic traversal**
All traversal over events, nodes, or edges uses explicitly sorted iteration order:
`sorted(collection, key=lambda x: x.{stable_field})`. Iteration order is never
left to dict insertion order, set ordering, or platform hash randomization.

**2.3 Canonical serialization compatibility**
Every signal record is serializable with:
```python
json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```
producing byte-identical output across all runs and PYTHONHASHSEED values.

**2.4 No side effects**
Signal extraction functions are pure. They do not write to ledger, modify graph
state, append to topology, or produce any observable effect beyond their return value.

**2.5 Source reference preservation**
Every signal record must carry the exact message_id or claim_id of the event(s) from
which it was derived. No signal is anonymous.

**2.6 Observed / Derived / Unresolved discipline**
Every signal must be explicitly classified as one of:
- `OBSERVED` — directly readable from artifact fields without inference
- `DERIVED` — computed from two or more OBSERVED values by a defined rule
- `UNRESOLVED` — the required source data is absent or structurally incomplete

---

## 3. Deterministic Signal Extraction Model

Signal extraction proceeds in three stages:

**Stage 1: Artifact loading**
Load frozen artifacts via replay functions only:
- `replay_transcript_events(ledger_path)` → event list
- `build_epistemic_graph(events)` → graph
- `claim_status_snapshot(graph)` → flat status dict

Input is treated as immutable. No field is written or appended.

**Stage 2: Signal computation**
Apply per-signal extraction rules (Section 4) in deterministic sorted order over
the loaded artifact. Each rule returns a signal record dict.

**Stage 3: Signal record construction**
Each signal record is a plain JSON-safe dict with mandatory fields:
```
{
    "signal_type":    str,       # signal category name (Section 4)
    "status":         str,       # "OBSERVED" | "DERIVED" | "UNRESOLVED"
    "value":          any,       # the measured value (int, float, str, list, or null)
    "source_refs":    list[str], # message_ids or claim_ids the signal was derived from
    "extraction_rule": str,      # name of the deterministic rule applied
    "missing_data":   bool,      # true if any required source field was absent
}
```

Signal records are returned as a sorted tuple ordered by `(signal_type, source_refs[0])`.

---

## 4. Signal Categories

### 4.1 Disagreement Density

**Input artifacts:** epistemic graph nodes and edges with relations `attacks`,
`evidence_against`, `critique_of`.

**Extraction rule:** `disagreement_density`
Count edges with `relation in {"attacks", "evidence_against", "critique_of"}` divided
by total edge count. Iteration order: `sorted(edges, key=lambda e: (e.source, e.target))`.

**Canonical ordering rule:** sorted by source claim_id, then target claim_id.

**Ambiguity handling:** If edge count is zero, value is `null` and status is
`UNRESOLVED` (denominator undefined).

**Uncertainty handling:** Missing epistemic_status on a node does not suppress the
edge count. The edge relation is the authoritative field.

**Status:** `OBSERVED` — counts are read directly from graph structure.

### 4.2 Unresolved Critique Detection

**Input artifacts:** epistemic graph nodes with `claim_type == "hypothesis"` or
`role == "critique"` and `epistemic_status in {"proposed", "contested"}`.

**Extraction rule:** `unresolved_critique_scan`
Walk nodes in `sorted(nodes, key=lambda n: n.claim_id)` order. A critique is
unresolved if it has no incoming edge with `relation in {"supports", "attacks"}`
from any arbiter-role node.

**Canonical ordering rule:** source_refs sorted alphabetically.

**Ambiguity handling:** If no arbiter-role node exists in the graph, all critiques
are classified as `UNRESOLVED` with `missing_data=True`.

**Status:** `DERIVED` — requires joining node attributes with edge structure.

### 4.3 Arbiter Deferral Detection

**Input artifacts:** transcript events with `role == "arbiter"` and content
matching a fixed string set: `{"deferred", "pending", "no consensus"}`.

**Extraction rule:** `arbiter_deferral_scan`
Walk transcript events in `sorted(events, key=lambda e: e["message_id"])` order.
Match arbiter events whose content contains any deferral marker (case-insensitive,
fixed vocabulary — no regex, no ML).

**Canonical ordering rule:** sorted by message_id.

**Ambiguity handling:** If an arbiter event contains both a resolution and a deferral
marker, status is `UNRESOLVED` and both markers are recorded in `source_refs`.

**Status:** `OBSERVED` — content fields are read directly.

### 4.4 Repeated Failure Pattern Extraction

**Input artifacts:** execution ledger events with `event_type == "execution.step"`
and `status == "failed"`.

**Extraction rule:** `repeated_failure_scan`
Walk execution events in `sorted(events, key=lambda e: e.get("event_id", ""))` order.
Group by `step` field. A step with failure count ≥ 2 is a repeated failure.

**Canonical ordering rule:** groups sorted by step name, then by event_id within group.

**Ambiguity handling:** If `step` field is absent, the event is excluded from
grouping and recorded as `missing_data=True` in a separate record.

**Status:** `DERIVED` — requires counting across grouped events.

### 4.5 Confidence-Outcome Gap Detection

**Input artifacts:** epistemic graph nodes with `confidence` field present; outcome
inferred from `epistemic_status`.

**Extraction rule:** `confidence_outcome_gap_scan`
Walk nodes in `sorted(nodes, key=lambda n: n.claim_id)` order. For each node with
`confidence is not None` and `epistemic_status in {"refuted", "contested"}`:
gap = confidence (as declared). Record gap value and node claim_id.

**Canonical ordering rule:** sorted by claim_id.

**Ambiguity handling:** If `confidence` is present but `epistemic_status` is absent,
status is `UNRESOLVED`.

**Status:** `OBSERVED` — both fields are read directly from node attributes.

### 4.6 Provenance Decay Detection

**Input artifacts:** epistemic graph `dangling_refs` list and node edge structure.

**Extraction rule:** `provenance_decay_scan`
Count entries in `graph["dangling_refs"]` (already a sorted list).
Additionally count nodes with no incoming edges and no outgoing evidence edges —
these are isolated nodes that may represent provenance breaks.

**Canonical ordering rule:** dangling_refs list is already sorted in graph output.
Isolated node list sorted by claim_id.

**Ambiguity handling:** A dangling ref indicates a referenced message_id that was
not found in the event set. This is unambiguously OBSERVED absence, not inferred.

**Status:** `OBSERVED` for dangling_refs; `DERIVED` for isolated node count.

### 4.7 Goal Drift Detection

**Input artifacts:** transcript topology linearized order and role sequence.

**Extraction rule:** `goal_drift_scan`
Walk events in topological order (`topological_claim_order` output). Record the
sequence of `role` values. A drift marker is emitted if role sequence deviates from
the expected pattern defined at topology creation time. Expected pattern must be
provided as an explicit frozen string list — not inferred.

**Canonical ordering rule:** follows topological order, which is deterministic by
Kahn's algorithm with alphabetical tie-break.

**Ambiguity handling:** If no expected role sequence is provided, status is
`UNRESOLVED` — drift cannot be measured against an undefined baseline.

**Status:** `DERIVED` — requires a provided baseline role sequence.

### 4.8 Communication Overhead Metrics

**Input artifacts:** transcript event list; edges with `relation == "parent_claim_id"`.

**Extraction rule:** `communication_overhead_scan`
Count total transcript events, total parent_claim_id edges (thread depth indicator),
and events per sender. Walk events in `sorted(events, key=lambda e: e["message_id"])`.

**Canonical ordering rule:** per-sender counts dict sorted by sender name.

**Ambiguity handling:** Events missing `sender` field are counted under key
`"__unknown__"` and flagged with `missing_data=True`.

**Status:** `OBSERVED` — all counts read directly from event fields.

### 4.9 Resolution Efficiency Metrics

**Input artifacts:** transcript events; arbiter events; critique events.

**Extraction rule:** `resolution_efficiency_scan`
For each arbiter event, count the number of critique events that share the same
`parent_message_id` chain (i.e., are in the arbiter's ancestry per topological order).
Resolution efficiency = resolved_critiques / total_critiques_in_scope. Walk in
`sorted(events, key=lambda e: e["message_id"])` order.

**Canonical ordering rule:** sorted by arbiter message_id.

**Ambiguity handling:** If total_critiques_in_scope is zero, value is `null` and
status is `UNRESOLVED`.

**Status:** `DERIVED` — requires joining arbiter events with topology ancestry.

---

## 5. Canonical Traversal Semantics

All collection iteration in signal extraction must follow one of these explicit
patterns:

```python
# Events
for event in sorted(events, key=lambda e: e["message_id"]):
    ...

# Graph nodes
for node in sorted(graph["nodes"], key=lambda n: n.claim_id):
    ...

# Graph edges
for edge in sorted(graph["edges"], key=lambda e: (e.source, e.target, e.relation)):
    ...

# String collections (dangling_refs, role lists)
for item in sorted(collection):
    ...
```

No bare `for x in dict` or `for x in set` is permitted. No `dict.items()` without
wrapping in `sorted(...)`.

---

## 6. Ambiguity and Uncertainty Handling

**Rule 6.1 — Missing fields**
If a required field is absent from an artifact record, the signal is produced with
`status="UNRESOLVED"` and `missing_data=True`. The signal is not suppressed.

**Rule 6.2 — Empty collections**
If the input collection is empty (no events, no nodes, no edges), return a single
signal record with `value=null`, `status="UNRESOLVED"`,
`source_refs=[]`, `missing_data=True`.

**Rule 6.3 — Structural ambiguity**
If two or more extraction rules could apply to the same event (e.g., an event that
is both a critique and an arbiter deferral), both signals are emitted independently.
No merging or deduplication occurs.

**Rule 6.4 — No synthetic resolution**
`UNRESOLVED` is never collapsed into `OBSERVED` or `DERIVED` by inference, default
values, or heuristic fallback.

---

## 7. Replay Reconstruction Guarantees

**7.1** Given only a JSONL ledger file and this specification, any process can
re-extract all signals and produce byte-identical signal record tuples via:
```python
events = replay_transcript_events(ledger_path)
graph  = build_epistemic_graph(events)
```
followed by the extraction rules in Section 4, in sorted traversal order.

**7.2** Signal records contain only values that are JSON-serializable with
`json.dumps(sort_keys=True, separators=(",", ":"))`. No signal record contains
a dataclass, a set, or any non-JSON type.

**7.3** The `source_refs` list in every signal record contains only message_ids or
claim_ids that appear in the input artifact. No synthetic IDs are generated.

---

## 8. Failure Modes

| Failure | Detection | Handling |
|---|---|---|
| Required artifact absent | `FileNotFoundError` at load time | Stop; do not emit signals |
| Required field missing in event | field access returns `None` | Emit `UNRESOLVED` signal |
| Dangling ref in graph | recorded in `graph["dangling_refs"]` | Emit provenance decay signal |
| Empty event list | collection length == 0 | Emit `UNRESOLVED` for all signal types |
| Cyclic graph | `detect_cycles(graph)` returns non-empty | Record cycle signal; do not compute topology-dependent signals |
| Denominator zero | explicit check before division | Set value to `null`, status to `UNRESOLVED` |

---

## 9. Explicit Non-Goals

This specification does NOT define:

- how signals are aggregated into rubric scores (→ Phase 1C Rubric Spec)
- how rubric outcomes influence protocol behavior (→ explicitly forbidden)
- adaptive thresholds that change based on signal history
- ML-based signal classification
- probabilistic signal weighting
- heuristic edge inference when provenance is incomplete
- recursive normalization of nested claim payloads
- real-time streaming signal extraction
- any form of runtime mutation

---

## 10. Future Compatibility Boundaries

**10.1** New signal types may be added in future phases by adding a new subsection
to Section 4. Existing signal type names and `extraction_rule` strings are frozen
once the first implementation is committed.

**10.2** The signal record schema (Section 3) may gain new optional fields provided
they have `null` defaults. Removing or renaming existing fields is a breaking change.

**10.3** The canonical traversal patterns (Section 5) are frozen. Any change to
iteration order requires a version increment in this document.

**10.4** This spec is a dependency of the rubric contract. The rubric contract must
reference signal_type names exactly as defined here.
