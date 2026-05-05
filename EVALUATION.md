# BCLAW2 Evaluation Layer

## Current Status

A minimal evaluation layer is now active. It surfaces existing pipeline signals without scoring, ranking, selecting, or self-modifying.

## Available Conflict Signals

- `conflict` flag — marks individual records where duplicate ids were resolved
- `conflict_count` — total number of conflicted records in output
- `conflict_ids` — list of ids that had conflicts, in output order
- `strategies_differ` — True when keep_first and keep_last produce different outputs

## Evaluation Fields (All Available via return_summary=True)

- `evaluation_input` — structured signal dict (`strategies_compared`, `outputs_differ`, `conflict_count`, `conflict_ids`)
- `evaluation_snapshot` — full context capture (`input_records`, `output_records`, `evaluation_input`)
- `evaluation_triggered` — invocation flag; `True` only when `enable_evaluation=True`
- `evaluation_result` — first deterministic evaluation output (see below)

## evaluation_result (First Deterministic Output)

When `enable_evaluation=True` and `return_summary=True`, `evaluation_result` contains:

```
{
  "status": "evaluated",
  "outputs_differ": <copied from evaluation_input>,
  "conflict_count": <copied from summary>,
  "consistency_check": <True if outputs_differ and conflict_count match their source values>,
  "evaluation_details": {
    "strategy_used": <pipeline strategy parameter>,
    "compared": <evaluation_input.strategies_compared>
  }
}
```

These values are copied from existing verified signals — no new computation, scoring, ranking, selection, or learning occurs. `consistency_check` is the first internal validation of evaluation output: it compares `evaluation_result` fields against their source values and returns `True` when they match. It performs no ranking, selection, learning, or pipeline feedback. `evaluation_details` exposes evaluation context only — `strategy_used` and `compared` are passed through from pipeline inputs without modification.

## What This Is Not

**This is still not recursive self-improvement.** Evaluation only surfaces signals already present in the pipeline. No output is selected, ranked, or fed back into the pipeline. No model decision is made based on these values. Human relay and explicit directed steps remain required for any change.

## Future Evaluation Layer (Not Yet Implemented)

- Compare and select between alternative outputs
- Score or rank based on defined, testable criteria
- Require rollback capability on failure
- Require automated test execution and audit trail

## evaluation_comparison (Available with compare_strategies + enable_evaluation)

When `compare_strategies=True`, `return_summary=True`, and `enable_evaluation=True`, the summary includes `evaluation_comparison` containing `keep_first` and `keep_last` — each a full `evaluation_result`-structured dict for that strategy.

This structure holds multiple evaluated outputs side by side. It enables comparison but does not choose between results — no selection, ranking, or pipeline feedback occurs.

## preferred_strategy (First Preference Signal — Observational Only)

`evaluation_comparison` now includes `preferred_strategy`:

- `"keep_first"` when `outputs_differ == True`
- `None` when outputs are identical

This is the first explicit preference signal. It is a deterministic fixed rule — not a learned or scored preference. It is **observational only** and is not executed as a decision, does not change pipeline output, and does not feed back into execution. No automatic selection occurs.

## apply_preference (First Controlled Execution of Preference)

`run_pipeline` accepts `apply_preference=False` (default). When set to `True` alongside `compare_strategies=True`, `return_summary=True`, and `enable_evaluation=True`:

- If `preferred_strategy` is not `None`, the returned output switches to that strategy's result.
- Otherwise the default output is returned unchanged.

This is the first controlled execution of a preference signal. It is **user-triggered, not autonomous** — all four flags must be explicitly set. No automatic selection occurs without explicit invocation.

**This is still not RSI.** Preference execution requires human instruction on every call. The system cannot invoke `apply_preference` on itself, cannot modify the preference rule, and cannot feed results back into its own execution loop.

## preference_applied (Audit Signal for Controlled Execution)

When `apply_preference=True`, the summary includes `preference_applied`:

- `True` if the output was switched to the preferred strategy's result
- `False` if no switch occurred (e.g. `preferred_strategy` was `None`)

This field enables traceability of preference application — every execution that uses `apply_preference` produces a verifiable record of whether the preference was acted upon. It is purely observational and does not affect output or pipeline behavior.

## override_strategy (Manual Override Layer)

`run_pipeline` accepts `override_strategy=None` (default). When `apply_preference=True` and `override_strategy` is set to `"keep_first"` or `"keep_last"`, it takes precedence over `preferred_strategy`.

**Control hierarchy:**

1. `override_strategy` (explicit human override — highest priority)
2. `preferred_strategy` (deterministic system preference)
3. Default pipeline output (no preference or override active)

This is deterministic and requires explicit human instruction. The system cannot set `override_strategy` on its own, cannot modify the preference rule, and cannot invoke this path without all required flags being set. No autonomy is introduced.

## execution_mode (Execution-Path Visibility Signal)

When `return_summary=True`, the summary includes `execution_mode`:

- `"default"` — no `apply_preference`; standard pipeline output
- `"preferred"` — `apply_preference=True` without `override_strategy`; output follows `preferred_strategy`
- `"override"` — `override_strategy` was used; output follows the explicit human override

This field enables tracing how the output was produced on any given pipeline call. It is purely observational and does not affect pipeline behavior or output selection.

## rationale (Explanation Layer for Preference Signal)

`evaluation_comparison` now includes `rationale` — a string explaining why `preferred_strategy` was chosen:

- `"keep_first selected due to deterministic rule when outputs differ"` when `outputs_differ == True`
- `"no preference applied because outputs are identical"` when outputs are identical

This increases transparency of the evaluation system without increasing its intelligence. The wording is fixed and deterministic — derived from `outputs_differ` only, no new decision logic is introduced.

## comparison_summary (High-Level Comparison Insight)

`evaluation_comparison` now includes `comparison_summary`:

- `"strategies produce different outputs"` when `outputs_differ == True`
- `"strategies produce identical outputs"` when `outputs_differ == False`

This provides a single, human-readable summary of the comparison result. It summarizes differences without influencing behavior — purely descriptive, no decision logic introduced.

## difference_detail (Structured Difference Signal)

`evaluation_comparison` now includes `difference_detail`:

- `"outputs differ in at least one field"` when `outputs_differ == True`
- `"no differences between outputs"` when `outputs_differ == False`

This provides minimal comparison depth without deeper analysis — no field-level inspection is performed. The string is derived solely from the existing `outputs_differ` boolean and is purely descriptive.

## preference_policy (Configurable Deterministic Preference Rule)

`run_pipeline` accepts `preference_policy="keep_first"` (default). This replaces the prior hardcoded `"keep_first"` preference. When `outputs_differ==True`, `preferred_strategy` is set to the value of `preference_policy`. Currently supported values: `"keep_first"`, `"keep_last"`.

If `outputs_differ==False`, `preferred_strategy` remains `None` regardless of policy. The policy does not execute unless `apply_preference=True` is also set.

The policy is an explicit caller input — it is not learned, inferred, or set autonomously. It is a deterministic configuration value, not an intelligent decision.

## Input Validation (Deterministic Control Protection)

All control inputs (`strategy`, `override_strategy`, `preference_policy`) are validated before any execution begins. Invalid values raise `ValueError` immediately. This protects the deterministic control guarantee — no execution path can be entered with an undefined or ambiguous configuration.

## prefer_lower_conflict (First Evaluation-Based Policy)

`"prefer_lower_conflict"` is the first policy that makes a decision based on evaluated output signals rather than a fixed rule. It compares `conflict_count` between `keep_first` and `keep_last` evaluation results and selects the strategy with the lower count. Fallback: `"keep_first"` when counts are equal.

**Current limitation:** Under the current fusion model, both strategies produce identical `conflict_count` for any given duplicate-id set. The policy structure is correct and deterministic, but the equal-count fallback is always triggered in practice. The policy will differentiate once fusion behavior produces divergent conflict counts.

**No learning, no autonomy, no self-modification.** The decision is fully deterministic and based only on existing evaluated signals.

## divergence_detected (Clean Signal for Meaningful Strategy Divergence)

`evaluation_comparison` now includes `divergence_detected`:

- `True` when `keep_first_output != keep_last_output` (simple structural comparison)
- `False` when outputs are structurally identical

This provides a clean, unambiguous signal for when strategies truly produce different results. It prepares future policies to act only when genuine divergence exists, but does not affect execution or pipeline behavior on its own.

## losing_strategy_reason (Contrastive Explanation Signal)

`evaluation_comparison` now includes `losing_strategy_reason`:

- `"keep_last not selected based on policy conditions"` when `preferred_strategy == "keep_first"`
- `"keep_first not selected based on policy conditions"` when `preferred_strategy == "keep_last"`
- `"no strategy selected due to no meaningful divergence"` when `preferred_strategy == None`

This explains why the alternative strategy was not chosen. It is a contrastive explanation signal — it increases evaluation transparency without changing behavior, introducing decision logic, or affecting pipeline output.

## preference_strength (Deterministic Symbolic Decision-Strength Signal)

`evaluation_comparison` now includes `preference_strength`:

| Value | Condition |
|-------|-----------|
| `"none"` | `preferred_strategy == None` — **verified reachable** |
| `"weak"` | `divergence_detected == False` but preferred is set — **not currently reachable** under existing fusion behavior |
| `"moderate"` | `divergence_detected == True`, conflict counts equal — **verified reachable** |
| `"strong"` | `divergence_detected == True`, conflict counts differ — **not currently reachable** under existing fusion behavior |

`preference_strength` is a symbolic categorical signal — it is **not** a confidence score, probability, or ROI measure. It prepares for future policy arbitration by providing a discrete, deterministic readout of how meaningful a preference decision is, based only on `preferred_strategy`, `divergence_detected`, and `conflict_count`. No behavior change, no probabilistic scoring, no learning.
