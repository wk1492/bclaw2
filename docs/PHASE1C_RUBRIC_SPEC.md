# Phase 1C: Deterministic SSRE Rubric Contracts

**Status:** Design specification — no implementation
**Depends on:** PHASE1C_SIGNAL_EXTRACTION_SPEC.md, BCLAW2 freeze checkpoint
**Base substrate:** frozen signal records produced by signal extraction layer

---

## 1. Objective

Define how the SSRE converts extracted deterministic signals into stable, labeled
evaluation outcomes. The rubric is a pure function: given the same signal records,
it always produces the same labeled output. It classifies; it does not optimize,
tune, or mutate.

The rubric layer is the final observational stage. Its output is a labeled evaluation
record that is auditable, replay-reconstructable, and provenance-traced. It cannot
influence runtime behavior, alter orchestration, or modify replay state.

---

## 2. Architectural Invariants

**2.1 Purely observational**
The rubric evaluator reads signal records and produces labeled output. It writes
nothing. It mutates nothing. It calls no external service.

**2.2 Fixed thresholds and weights**
All numeric thresholds and weights used in rubric aggregation are static values
defined explicitly in this document. They do not change at runtime. They are not
learned. They are not tuned. Any change to threshold or weight values requires a
version increment of this document.

**2.3 Deterministic aggregation**
Given identical input signal records in identical sorted order, the rubric always
produces identical output. No randomness, no environment sensitivity.

**2.4 Canonical serialization compatibility**
Every rubric output record is serializable with:
```python
json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```
producing byte-identical output across all runs.

**2.5 Provenance traceability**
Every rubric output record identifies the exact signal records that contributed to
its outcome via `contributing_signals: list[str]` (signal_type values, sorted).

**2.6 UNCERTAIN is first-class**
UNCERTAIN is never collapsed, coerced, or resolved by inference. A rubric that
cannot determine an outcome emits UNCERTAIN — it does not guess.

**2.7 SSRE_RUBRIC_VERSION**
This specification defines `SSRE_RUBRIC_VERSION = 1`. All evaluation output records
must carry this version number as `rubric_version: 1`.

---

## 3. Rubric Model

The rubric evaluator operates as a two-stage pipeline:

**Stage 1: Signal ingestion**
Accept a sorted tuple of signal records (as defined in
PHASE1C_SIGNAL_EXTRACTION_SPEC.md Section 3). Validate that each record has the
required mandatory fields. Records with `missing_data=True` are ingested but
trigger INSUFFICIENT_PROVENANCE weighting (Section 4.3).

**Stage 2: Label determination**
Apply aggregation rules (Section 4) to produce a single `EvaluationRecord`:

```
{
    "rubric_version":        int,      # always 1 at this spec version
    "outcome":               str,      # one of the 7 label types (Section 5)
    "confidence_class":      str,      # "HIGH" | "MEDIUM" | "LOW" (Section 4.4)
    "contributing_signals":  list[str], # sorted list of signal_type values
    "unresolved_signals":    list[str], # sorted list of UNRESOLVED signal_types
    "missing_provenance":    bool,      # true if any signal had missing_data=True
    "aggregation_path":      list[str], # ordered list of rules applied, for audit
    "source_refs":           list[str], # union of all source_refs from contributing signals, sorted
}
```

---

## 4. Deterministic Aggregation Rules

### 4.1 Primary aggregation

Rules are applied in fixed priority order. The first rule that fires determines the
outcome. Priority is static and cannot be altered at runtime.

| Priority | Rule name | Condition | Outcome |
|---|---|---|---|
| 1 | `missing_replay` | Event list was empty at extraction time | INCOMPLETE_REPLAY |
| 2 | `cycle_detected` | `detect_cycles` returned non-empty | INCOMPLETE_REPLAY |
| 3 | `no_provenance` | All signals have `missing_data=True` | INSUFFICIENT_PROVENANCE |
| 4 | `arbiter_deferral` | Any `arbiter_deferral` signal with `value > 0` | ARBITER_DEFERRAL |
| 5 | `conflict_detected` | disagreement_density ≥ 0.5 AND unresolved_critique > 0 | CONFLICTED |
| 6 | `failure_pattern` | repeated_failure_scan value ≥ 2 | FAILURE |
| 7 | `success_conditions` | All criteria in Section 4.2 met | SUCCESS |
| 8 | `default` | No prior rule fired | UNCERTAIN |

### 4.2 SUCCESS conditions (all must hold)

A SUCCESS outcome requires all of the following to be simultaneously true:

- `disagreement_density` signal value < 0.25
- `unresolved_critique_scan` signal value == 0
- `arbiter_deferral_scan` signal value == 0
- `repeated_failure_scan` signal value < 2
- No signal has `status == "UNRESOLVED"`
- No signal has `missing_data == True`

If any condition is absent (signal not extracted), SUCCESS cannot be emitted.

### 4.3 INSUFFICIENT_PROVENANCE weighting

An evaluation is classified as having insufficient provenance if:

- More than 50% of expected signal types are `UNRESOLVED` or `missing_data=True`
- OR the `provenance_decay_scan` signal reports dangling_ref_count > 0 AND
  isolated_node_count > 0 simultaneously

Threshold: 50%. This value is static. It is not tunable at runtime.

### 4.4 Confidence class assignment

Confidence class reflects how much of the signal set was fully OBSERVED (not
DERIVED or UNRESOLVED):

| OBSERVED signal fraction | Confidence class |
|---|---|
| ≥ 0.75 | HIGH |
| ≥ 0.40 | MEDIUM |
| < 0.40 | LOW |

Fraction = count(OBSERVED signals) / count(total signal records ingested).
If total count is zero, confidence_class is `"LOW"`.

These thresholds (0.75, 0.40) are static. They are not learned or tuned.

### 4.5 Tie handling

If two rules at different priorities both apply (theoretically possible in edge
cases), the lower priority number (higher priority) wins. This rule is absolute.
No tie-breaking heuristic exists.

---

## 5. Label Semantics

### 5.1 SUCCESS

All observable criteria were met. No unresolved critiques. No repeated failures.
No arbiter deferral. Provenance is complete. Disagreement density is below threshold.

This label does NOT mean the system is correct, only that the observational criteria
were satisfied within the frozen artifact set.

### 5.2 FAILURE

A repeated failure pattern was detected (≥ 2 occurrences of the same step failing)
and no higher-priority rule fired first. The failure is traceable to specific
execution step events via `source_refs`.

### 5.3 UNCERTAIN

No rule fired clearly enough to classify the outcome. The evaluator refuses to
fabricate a classification. UNCERTAIN is a valid, complete, non-degraded outcome.
It signals that more artifact data is required before classification is possible.

UNCERTAIN must never be silently promoted to SUCCESS or FAILURE.

### 5.4 CONFLICTED

High disagreement density combined with unresolved critiques. The system produced
competing claims that were not arbitrated to resolution. Traceable to specific
claim_ids via `source_refs`.

### 5.5 INSUFFICIENT_PROVENANCE

The artifact set does not contain enough provenance data to support classification.
Dangling references, isolated nodes, or excessive UNRESOLVED signals indicate the
ledger captured an incomplete replay.

This label does not imply system failure — it implies insufficient evidence.

### 5.6 INCOMPLETE_REPLAY

The replay artifact was structurally unusable: either the event list was empty or
the epistemic graph contained a cycle (which prevents topological traversal).
No classification can proceed until a complete, acyclic replay is available.

### 5.7 ARBITER_DEFERRAL

An arbiter event explicitly deferred resolution using a known deferral marker. This
is observable from transcript content and is neither success nor failure. It requires
human review before the next replay can be classified.

---

## 6. Uncertainty Preservation Rules

**Rule 6.1** UNCERTAIN signals accumulate — they do not cancel each other out. Each
additional UNRESOLVED signal increases the `unresolved_signals` list but does not
itself change the outcome (the default rule already maps to UNCERTAIN).

**Rule 6.2** The rubric evaluator never assigns a default value to a missing field.
If a required signal type was not extracted, its absence is recorded in
`unresolved_signals` and contributes to the confidence class calculation.

**Rule 6.3** A rubric outcome of UNCERTAIN with `confidence_class="HIGH"` is valid
and means: we are highly confident that we cannot classify this replay. It does not
imply a bug.

**Rule 6.4** The rubric must never use string matching, fuzzy logic, or partial
matches to infer an OBSERVED signal from a DERIVED or UNRESOLVED one.

---

## 7. Provenance Traceability Requirements

**7.1** Every `EvaluationRecord` must carry `source_refs`: the sorted union of all
`source_refs` from every contributing signal record. This allows any reader to trace
from outcome → signal → artifact event.

**7.2** The `aggregation_path` field records the ordered list of rule names evaluated
(e.g., `["missing_replay", "cycle_detected", "no_provenance", "arbiter_deferral"]`
up to and including the rule that fired). This makes the aggregation fully auditable.

**7.3** An `EvaluationRecord` with no contributing signals (all signals were
UNRESOLVED with empty `source_refs`) must carry `source_refs=[]` explicitly — not
omit the field.

**7.4** No `source_refs` entry may be a synthetic ID. Every entry must be a
message_id or claim_id that appears in the input artifact ledger.

---

## 8. Replay Reconstruction Guarantees

**8.1** Given the same input signal records in the same sorted order, the rubric
always produces a byte-identical `EvaluationRecord`. This is guaranteed by the
deterministic priority-rule evaluation in Section 4.1 and the fixed thresholds in
Sections 4.2–4.4.

**8.2** The `EvaluationRecord` is fully JSON-safe and canonical-serializable. It
contains no dataclasses, no sets, no floats that depend on floating-point ordering.

**8.3** The rubric does not maintain inter-call state. Each call is independent.
Two calls with the same inputs produce identical outputs regardless of call order
or timing.

---

## 9. Failure Modes

| Failure | Detection | Handling |
|---|---|---|
| Signal record missing required field | KeyError at ingestion | Reject record; emit INSUFFICIENT_PROVENANCE |
| All signals UNRESOLVED | count check at Stage 2 | Emit INSUFFICIENT_PROVENANCE via rule 3 |
| Cyclic graph signal present | signal_type == "cycle_detected" | Emit INCOMPLETE_REPLAY via rule 2 |
| Empty signal input | len(records) == 0 | Emit INCOMPLETE_REPLAY via rule 1 |
| Unknown signal_type | not in defined set | Log as unexpected; do not suppress; treat as UNRESOLVED |
| Non-JSON value in signal record | json.dumps raises | Hard failure; do not emit partial output |

---

## 10. Explicit Non-Goals

This specification does NOT define:

- how rubric outcomes influence protocol behavior (explicitly forbidden)
- adaptive threshold tuning based on historical outcomes
- ML classifiers for any signal or outcome
- probabilistic outcome scoring
- Bayesian inference over signal combinations
- runtime weight learning or reinforcement
- automatic prompt or protocol modification based on outcome labels
- orchestration routing based on rubric output
- streaming or incremental evaluation
- multi-version rubric merging
- any form of autonomous self-correction

---

## 11. Future Compatibility Boundaries

**11.1** New label types require a version increment to `SSRE_RUBRIC_VERSION`. The
current 7 labels (Section 5) are frozen at version 1.

**11.2** New priority rules in Section 4.1 must be inserted at an explicit priority
number and must not reorder existing rules. Reordering is a breaking change.

**11.3** New fields in `EvaluationRecord` must have explicit `null` defaults. Removing
or renaming existing fields is a breaking change.

**11.4** The fixed thresholds (0.25 disagreement, 0.50 provenance, 0.75/0.40
confidence, 2 failure count) are frozen at version 1. Changing any threshold
requires a version increment and a new committed specification.

**11.5** This spec is a dependency of any future SSRE implementation. An implementation
may only emit label types defined here. Emitting an unlisted label is a contract
violation.
