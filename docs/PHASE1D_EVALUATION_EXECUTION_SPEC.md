# Phase 1D: Deterministic Evaluation Execution Flow

**Status:** Design specification — no implementation
**Depends on:** PHASE1C_SIGNAL_EXTRACTION_SPEC.md, PHASE1C_RUBRIC_SPEC.md,
BCLAW2 freeze checkpoint (HEAD f13ef16)
**SSRE_EXECUTION_VERSION:** 1

---

## 1. Objective

Define the deterministic execution lifecycle that transforms frozen replay artifacts
into immutable observational evaluation records. The lifecycle is a bounded
transaction pipeline: it reads, validates, aggregates, labels, and emits. It does
not optimize, route, adapt, or influence any downstream system.

The execution flow is the integration point between:
- the signal extraction layer (PHASE1C_SIGNAL_EXTRACTION_SPEC.md)
- the rubric contract (PHASE1C_RUBRIC_SPEC.md)
- the append-only ledger substrate (BCLAW2 freeze checkpoint)

Its output — a signed, immutable `EvaluationRecord` — is the terminal artifact.
It cannot feed back into the replay system that produced it.

---

## 2. Architectural Invariants

**2.1 Deterministic transaction model**
The evaluation execution pipeline behaves as a pure function:
`execute_evaluation(ledger_path, run_id) → EvaluationRecord`.
Same inputs always produce the same output. No runtime state persists between calls.

**2.2 Append-only evaluation recording**
`EvaluationRecord` outputs are appended to an evaluation ledger using the same
`LedgerWriter` hash-chain contract as the transcript ledger. They are never updated,
overwritten, or retroactively corrected.

**2.3 No feedback path**
The `EvaluationRecord` does not feed back into the transcript ledger, the epistemic
graph, the topology, or any orchestration system. It is a terminal observational
artifact.

**2.4 Strict stage isolation**
Each pipeline stage (Section 3) receives only the output of the preceding stage.
No stage may read a future stage's output, skip a prior stage, or short-circuit the
pipeline. Stage boundaries are explicit and auditable.

**2.5 Canonical serialization**
All intermediate and final outputs are serialized with:
```python
json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```
producing byte-identical results across all runs and PYTHONHASHSEED values.

**2.6 Provenance continuity**
Every artifact produced by the pipeline carries `source_refs` traceable to
message_ids and claim_ids in the input ledger. No artifact is anonymous.

**2.7 SSRE_EXECUTION_VERSION**
All `EvaluationRecord` outputs carry `execution_version: 1`. Any change to the
pipeline stages, ordering, or rejection conditions requires a version increment.

---

## 3. Evaluation Execution Lifecycle

The pipeline consists of exactly 10 ordered stages. They execute sequentially.
No stage may be parallelized, reordered, or skipped. Each stage either produces
a valid output for the next stage or emits a terminal failure record and halts.

```
Stage 1:  Replay Artifact Validation
    ↓
Stage 2:  Provenance Integrity Verification
    ↓
Stage 3:  Signal Extraction Consumption
    ↓
Stage 4:  Rubric Evaluation Ordering
    ↓
Stage 5:  Deterministic Aggregation
    ↓
Stage 6:  Conflict Resolution Handling
    ↓
Stage 7:  Uncertainty Preservation
    ↓
Stage 8:  Final Observational Emission
    ↓
Stage 9:  Immutable Evaluation Recording
    ↓
Stage 10: Replay Reconstruction Validation
```

### Stage 1 — Replay Artifact Validation

**Input:** `ledger_path` (filesystem path to JSONL ledger file), `run_id` (str)

**Operation:**
1. Verify the ledger file exists and is non-empty.
2. Call `verify_mixed_ledger(ledger_path)` and confirm `result["ok"] is True`.
3. Call `replay_transcript_events(ledger_path)` and confirm the returned list is
   non-empty.
4. Confirm all returned events carry `event_type == "transcript.message"`.

**Output:** validated event list (immutable — not modified in subsequent stages)

**Rejection conditions:**
- File absent → emit `STAGE1_ARTIFACT_ABSENT` failure record; halt.
- `verify_mixed_ledger` returns `ok=False` → emit `STAGE1_HASH_CHAIN_BROKEN`; halt.
- Event list empty → emit `STAGE1_EMPTY_REPLAY`; halt.

**Determinism guarantee:** `replay_transcript_events` is deterministic given the
same ledger bytes. Validated event list is identical across runs.

**Isolation rule:** Stage 1 does not build any graph, compute any topology, or
extract any signal. It only validates the raw artifact.

### Stage 2 — Provenance Integrity Verification

**Input:** validated event list from Stage 1

**Operation:**
1. Call `build_epistemic_graph(events)`.
2. Call `validate_epistemic_graph(graph)` and confirm it returns `[]`.
3. Call `detect_cycles(graph)` and confirm it returns `[]`.
4. Record `graph["dangling_refs"]` for propagation to Stage 3.

**Output:** validated `graph` dict (frozen — not modified in subsequent stages)

**Rejection conditions:**
- `validate_epistemic_graph` returns non-empty errors → emit `STAGE2_GRAPH_INVALID`
  with error list; halt.
- `detect_cycles` returns non-empty → emit `STAGE2_CYCLE_DETECTED` with cycle node
  list; halt.

**Determinism guarantee:** `build_epistemic_graph` is input-order independent and
produces sorted node/edge tuples. `validate_epistemic_graph` and `detect_cycles`
are pure deterministic functions.

**Isolation rule:** Stage 2 does not extract signals or apply rubric rules. It only
validates graph structural integrity.

### Stage 3 — Signal Extraction Consumption

**Input:** validated event list (Stage 1), validated graph (Stage 2)

**Operation:**
Apply all signal extraction rules defined in PHASE1C_SIGNAL_EXTRACTION_SPEC.md
Section 4, in the following fixed order:
1. `disagreement_density`
2. `unresolved_critique_scan`
3. `arbiter_deferral_scan`
4. `repeated_failure_scan`
5. `confidence_outcome_gap_scan`
6. `provenance_decay_scan`
7. `goal_drift_scan`
8. `communication_overhead_scan`
9. `resolution_efficiency_scan`

Each extraction rule is applied independently. Results are collected into a sorted
tuple of signal records ordered by `(signal_type, source_refs[0] if source_refs else "")`.

**Output:** sorted tuple of signal records conforming to the schema in
PHASE1C_SIGNAL_EXTRACTION_SPEC.md Section 3.

**Rejection conditions:** No signal extraction failure halts the pipeline. Failures
within individual rules produce `UNRESOLVED` signal records (per extraction spec
Rule 6.1). The pipeline continues with all signals including `UNRESOLVED` ones.

**Determinism guarantee:** Fixed rule application order plus sorted output tuple
guarantees identical signal record tuples for identical inputs.

**Isolation rule:** Signal extraction is read-only over the event list and graph.
Neither is modified. Stage 3 does not apply rubric rules.

### Stage 4 — Rubric Evaluation Ordering

**Input:** sorted signal record tuple from Stage 3

**Operation:**
1. Count total signal records.
2. Count records with `status == "OBSERVED"`, `"DERIVED"`, and `"UNRESOLVED"`.
3. Count records with `missing_data == True`.
4. Compute `observed_fraction = count(OBSERVED) / len(records)` if len > 0, else 0.0.
5. Identify which of the 7 rubric label types (PHASE1C_RUBRIC_SPEC.md Section 5)
   are potentially triggered by the signal set, without yet determining priority winner.

**Output:** `RubricInput` dict:
```
{
    "signal_records":      tuple[dict],  # sorted signal record tuple (unchanged)
    "total_count":         int,
    "observed_count":      int,
    "derived_count":       int,
    "unresolved_count":    int,
    "missing_data_count":  int,
    "observed_fraction":   float,
    "candidate_outcomes":  list[str],    # sorted list of potentially triggered labels
}
```

**Determinism guarantee:** All counts are integer operations over a sorted tuple.
`observed_fraction` is a float division with explicit zero-denominator guard.

**Isolation rule:** Stage 4 does not determine the final outcome. It prepares the
input for deterministic aggregation. No rubric priority rule fires in this stage.

### Stage 5 — Deterministic Aggregation

**Input:** `RubricInput` from Stage 4

**Operation:**
Apply rubric priority rules from PHASE1C_RUBRIC_SPEC.md Section 4.1 in exact
priority order (1 through 8). Evaluate each rule as a boolean predicate against
the `RubricInput`. The first rule whose predicate evaluates to `True` determines
the outcome. Record the ordered list of rules evaluated as `aggregation_path`.

Priority rule predicates (in order):

| Priority | Rule | Predicate |
|---|---|---|
| 1 | `missing_replay` | `total_count == 0` |
| 2 | `cycle_detected` | `STAGE2_CYCLE_DETECTED` present in pipeline state |
| 3 | `no_provenance` | `missing_data_count == total_count AND total_count > 0` |
| 4 | `arbiter_deferral` | any signal with `signal_type=="arbiter_deferral_scan"` has `value > 0` |
| 5 | `conflict_detected` | `disagreement_density.value >= 0.25` AND `unresolved_critique_scan.value > 0` |
| 6 | `failure_pattern` | `repeated_failure_scan.value >= 2` |
| 7 | `success_conditions` | all SUCCESS conditions in rubric spec Section 4.2 met |
| 8 | `default` | always True (fallback) → UNCERTAIN |

**Output:** `AggregationResult` dict:
```
{
    "outcome":              str,       # winning label
    "aggregation_path":     list[str], # rules evaluated in order
    "winning_rule":         str,       # name of the rule that fired
    "contributing_signals": list[str], # sorted signal_types that contributed
}
```

**Determinism guarantee:** Fixed priority evaluation order over a deterministic
input. Tie-breaking is structural — lower priority number always wins. No
two rules fire simultaneously in a way that requires additional tie-breaking.

**Isolation rule:** Stage 5 does not write any record. It only determines the label.

### Stage 6 — Conflict Resolution Handling

**Input:** `AggregationResult` from Stage 5, signal records from Stage 3

**Operation:**
If `outcome == "CONFLICTED"`, collect all signals that contributed to the conflict:
signals with `signal_type in {"disagreement_density", "unresolved_critique_scan"}`.
Record their `source_refs` as the conflict evidence set (sorted).

If `outcome != "CONFLICTED"`, this stage is a pass-through: `AggregationResult`
is forwarded unchanged.

The conflict evidence set is NOT resolved. It is preserved as-is.

**Output:** `ConflictRecord` dict (or pass-through of `AggregationResult`):
```
{
    "outcome":            str,       # "CONFLICTED" or forwarded outcome
    "conflict_evidence":  list[str], # sorted source_refs of conflicting signals, or []
    "competing_signals":  list[str], # sorted signal_types in conflict, or []
}
```

**Conflict discipline:** Competing observations are preserved in full. No
forced convergence. No heuristic resolution. No fabricated consensus.

**Isolation rule:** Stage 6 does not alter signal values. It only records which
signals are in conflict.

### Stage 7 — Uncertainty Preservation

**Input:** all prior stage outputs

**Operation:**
Collect all `UNRESOLVED` signal records from Stage 3. Record their `signal_type`
values as `unresolved_signals` (sorted). Confirm that none were silently discarded.

Compute `missing_provenance = (missing_data_count > 0)`.

**Output:** `UncertaintyRecord` dict:
```
{
    "unresolved_signals":  list[str], # sorted signal_type values with UNRESOLVED status
    "missing_provenance":  bool,
    "unresolved_count":    int,
}
```

**Uncertainty discipline:** Every UNRESOLVED signal is explicitly named. None are
collapsed into OBSERVED or DERIVED. None are discarded.

**Isolation rule:** Stage 7 does not alter the outcome determined in Stage 5.

### Stage 8 — Final Observational Emission

**Input:** outputs of Stages 5, 6, 7; full signal record tuple from Stage 3

**Operation:**
Construct the final `EvaluationRecord` by merging all prior stage outputs:

```
{
    "execution_version":     int,       # SSRE_EXECUTION_VERSION = 1
    "rubric_version":        int,       # SSRE_RUBRIC_VERSION = 1 (from rubric spec)
    "run_id":                str,       # input run_id
    "outcome":               str,       # from Stage 5
    "confidence_class":      str,       # from rubric spec Section 4.4, computed over observed_fraction
    "contributing_signals":  list[str], # sorted; from Stage 5
    "unresolved_signals":    list[str], # sorted; from Stage 7
    "missing_provenance":    bool,      # from Stage 7
    "conflict_evidence":     list[str], # sorted; from Stage 6 (empty if not CONFLICTED)
    "aggregation_path":      list[str], # from Stage 5
    "source_refs":           list[str], # sorted union of source_refs from all contributing signals
    "dangling_refs":         list[str], # from Stage 2 graph["dangling_refs"]
}
```

`source_refs` is the sorted union of `source_refs` from every signal record whose
`signal_type` appears in `contributing_signals`.

**Output:** immutable `EvaluationRecord` dict. Once constructed, no field is modified.

**Determinism guarantee:** All fields are derived from deterministic prior stages.
The sort operations on list fields are explicit. The dict is constructed in fixed
key order.

**Isolation rule:** Stage 8 does not write to any ledger. It produces the record
in memory only.

### Stage 9 — Immutable Evaluation Recording

**Input:** `EvaluationRecord` from Stage 8

**Operation:**
Append the `EvaluationRecord` to the evaluation ledger using `LedgerWriter`.
The evaluation ledger is a separate JSONL file from the transcript ledger. It uses
the same hash-chain contract.

The `EvaluationRecord` is treated as the payload. `LedgerWriter` adds the standard
decoration fields (`event_hash`, `rolling_hash`, `previous_hash`, `timestamp`,
`event_id`). The decoration fields do not alter the `EvaluationRecord` content.

**Output:** appended ledger record with decoration fields. The returned record
(including decoration) is the durable artifact.

**Append-only discipline:** No evaluation record is ever updated, deleted, or
superseded in the ledger. A corrected evaluation is a new append, not a replacement.

**Determinism note:** `LedgerWriter` adds a wall-clock `timestamp`, which is the
sole non-deterministic field in the system. The `EvaluationRecord` payload fields
are all deterministic. The content-addressed `event_hash` is computed from the
deterministic payload only.

### Stage 10 — Replay Reconstruction Validation

**Input:** appended ledger record from Stage 9

**Operation:**
Verify that the appended record can be reconstructed by:
1. Loading the evaluation ledger line.
2. Stripping decoration fields (`timestamp`, `event_hash`, `event_id`,
   `rolling_hash`, `previous_hash`).
3. Confirming the remaining dict is byte-identical to the Stage 8 `EvaluationRecord`
   when serialized with `json.dumps(sort_keys=True, separators=(",", ":"))`.

**Output:** `ReconstructionResult` dict:
```
{
    "reconstruction_ok":  bool,
    "failure_reason":     str | null,  # null if ok
}
```

If `reconstruction_ok is False`, this is a critical substrate failure. Halt and
emit a `STAGE10_RECONSTRUCTION_FAILED` failure record. Do not suppress.

**Determinism guarantee:** The stripping of decoration fields and canonical
serialization are both deterministic. If Stage 8 was deterministic, Stage 10 will
always pass for the same run.

---

## 4. Deterministic Ordering Rules

**4.1 Stage sequence is fixed.** Stages 1–10 execute in order. No reordering.

**4.2 Signal extraction order is fixed** (Section 3, Stage 3). The 9 extraction
rules always run in the same named order. New rules may only be appended at the
end and require an `SSRE_EXECUTION_VERSION` increment.

**4.3 Rubric priority order is fixed** (Section 3, Stage 5). Rules 1–8 always
evaluate in ascending priority order. The first True predicate wins.

**4.4 All list fields in outputs are sorted.** No list is left in insertion order,
dict order, or set order.

**4.5 Float comparison uses explicit thresholds.** The disagreement_density
threshold is `>= 0.25` (not `> 0.24`). All float comparisons are stated as
`>=`, `>`, `==`, `<`, or `<=` against explicit static constants. No epsilon
comparisons. No fuzzy matching.

**4.6 Integer sentinel values.** Where a signal value is `null` (UNRESOLVED
denominator), it is treated as absent — it does not satisfy any numeric predicate.
Absent values never satisfy `>= 0`, `> 0`, or `== 0`.

---

## 5. Provenance Continuity Guarantees

**5.1** Every `EvaluationRecord` carries `source_refs` that trace to message_ids
and claim_ids in the input transcript ledger. The chain is:
```
EvaluationRecord.source_refs
  → signal_record.source_refs
    → message_id / claim_id in transcript ledger
      → event in JSONL ledger line
```

**5.2** `dangling_refs` from the epistemic graph are preserved in the
`EvaluationRecord` unchanged. They are not resolved, not suppressed, not inferred.

**5.3** The evaluation ledger record (Stage 9) is itself in the hash chain. Any
future reader can verify the `event_hash` of the evaluation record against the
stored payload, establishing tamper evidence.

**5.4** The `aggregation_path` in the `EvaluationRecord` provides a complete audit
trail of which rules were evaluated and which fired. No rule evaluation is hidden.

---

## 6. Aggregation Semantics

**6.1 Priority-first.** The first matching priority rule (Section 3, Stage 5)
determines the outcome. Subsequent rules are not evaluated for outcome purposes
but may still contribute to `aggregation_path` for audit purposes.

**6.2 Contributing signals.** A signal `contributes` if its `signal_type` is named
by the winning rule's predicate definition. All contributing signals are listed in
`contributing_signals`. Non-contributing signals are not suppressed — they remain
in the full signal tuple accessible from Stage 3.

**6.3 No weighted averaging.** The aggregation is a strict priority cascade, not a
weighted sum. Signal weights do not exist at the execution layer. Weights exist
only within individual rubric predicates (e.g., the confidence class thresholds
defined in PHASE1C_RUBRIC_SPEC.md Section 4.4).

**6.4 Confidence class.** The `confidence_class` field (`HIGH`, `MEDIUM`, `LOW`) is
computed from `observed_fraction` (Stage 4) using the static thresholds in
PHASE1C_RUBRIC_SPEC.md Section 4.4. It does not affect the `outcome` field.

---

## 7. Conflict Preservation Rules

**7.1** When `outcome == "CONFLICTED"`, the competing signals are preserved in full
in `conflict_evidence` and `competing_signals`. No signal is discarded to simplify
the record.

**7.2** Forced consensus is forbidden. The pipeline does not resolve conflicts by
choosing the stronger signal, the more recent signal, or the higher-confidence signal.

**7.3** A CONFLICTED record is a valid terminal output. It is not a failure state —
it is a faithfully observed disagreement state that requires human review.

**7.4** If the same `source_refs` appear in both a CONFLICTED and a non-CONFLICTED
signal, both records are preserved. No deduplication of source_refs across signals.

---

## 8. Failure Containment Model

**8.1 Stage halt semantics.** If a stage emits a failure record, the pipeline halts
immediately. No subsequent stage executes. The failure record is appended to the
evaluation ledger (via Stage 9 semantics) before halting.

**8.2 Failure record schema.**
```
{
    "execution_version":  int,    # SSRE_EXECUTION_VERSION
    "run_id":             str,
    "outcome":            str,    # "PIPELINE_FAILURE"
    "failure_stage":      int,    # stage number where failure occurred (1–10)
    "failure_code":       str,    # e.g. "STAGE1_ARTIFACT_ABSENT"
    "failure_detail":     str,    # human-readable, non-inferential description
    "source_refs":        list,   # [] if failure precedes signal extraction
}
```

**8.3 No silent recovery.** The pipeline does not attempt to repair malformed
artifacts, fill in missing provenance, or substitute default values for absent
fields. All failures are explicit and recorded.

**8.4 No heuristic repair.** A corrupt ledger line is not guessed at. A missing
event is not synthesized. A broken hash chain is not re-stitched.

**8.5 Failure records are immutable.** Once appended, a failure record is not
updated. A retry (if authorized by an external operator) produces a new ledger
append with a new `event_id`.

**8.6 Partial artifact corruption.** If `verify_mixed_ledger` reports failures in
`result["failures"]`, those failures are recorded in the Stage 1 failure record
verbatim. The original failure strings from `ledger_writer` are not paraphrased.

---

## 9. Immutable Output Guarantees

**9.1** Once Stage 8 constructs the `EvaluationRecord`, no field is modified by
Stage 9 or Stage 10. `LedgerWriter` adds decoration fields without touching
the payload.

**9.2** The evaluation ledger is append-only. The `LedgerWriter` contract
(BCLAW2 SUBSTRATE_CONTRACT.md Section 2–3) applies without modification.

**9.3** An `EvaluationRecord` represents a point-in-time observational snapshot
of the replay artifact at the time of evaluation. It does not represent the
current state of any mutable system.

**9.4** Corrections are new appends. If an operator determines that a prior
evaluation was based on a malformed artifact, a new evaluation is run against a
corrected artifact. The original record is not amended. Both records coexist in
the ledger with distinct `event_id` values.

---

## 10. Replay Reconstruction Guarantees

**10.1** Given only the evaluation ledger JSONL file, any process can reconstruct
the full `EvaluationRecord` by loading the line, stripping decoration fields, and
verifying the `event_hash`.

**10.2** Given only the transcript ledger JSONL file and this specification, any
process can re-run the full 10-stage pipeline and produce a byte-identical
`EvaluationRecord` payload (modulo the wall-clock `timestamp` decoration field
added by `LedgerWriter` in Stage 9 — which is excluded from the content-addressed
`event_hash`).

**10.3** The `aggregation_path` field in the `EvaluationRecord` allows any reader
to independently verify that the correct priority rule fired by re-evaluating the
same predicates against the same signal records.

**10.4** No intermediate pipeline state (Stage 1–7 outputs) needs to be persisted
for reconstruction. All intermediate state is re-derivable from the input ledger
and this specification.

---

## 11. Explicit Non-Goals

This specification does NOT define:

- how `EvaluationRecord` outputs influence protocol behavior (explicitly forbidden)
- adaptive threshold adjustment based on evaluation history
- ML-based classification at any stage
- probabilistic signal weighting or Bayesian aggregation
- runtime policy mutation based on evaluation outcomes
- automatic prompt or orchestration modification
- streaming or incremental pipeline execution
- distributed pipeline execution across multiple processes
- multi-ledger evaluation (each evaluation targets exactly one ledger file)
- self-healing artifact recovery
- heuristic provenance inference when source_refs are incomplete
- any form of autonomous correction or self-improvement

---

## 12. Future Compatibility Boundaries

**12.1** New pipeline stages must be inserted with explicit stage numbers and must
not reorder existing stages 1–10. Reordering is a breaking change requiring a
version increment of `SSRE_EXECUTION_VERSION`.

**12.2** The `EvaluationRecord` schema (Section 3, Stage 8) may gain new optional
fields with explicit `null` defaults. Removing or renaming existing fields is a
breaking change.

**12.3** The failure record schema (Section 8.2) may gain new optional fields.
`failure_code` values are extensible — new codes may be added for new halt
conditions without a version increment.

**12.4** Signal extraction rule names (Stage 3 fixed order) are frozen at version 1.
New rules may only be appended at position 10+ and require an
`SSRE_EXECUTION_VERSION` increment.

**12.5** This specification is a dependency of any future SSRE implementation.
An implementation that skips a stage, reorders stages, or omits any field from
`EvaluationRecord` is in violation of this contract.

**12.6** The wall-clock timestamp (Stage 9 decoration) is the only non-deterministic
field in the system at this version. Future specifications must not introduce
additional sources of non-determinism without explicit justification and version
increment.
