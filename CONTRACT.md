# BCLAW2 CONTRACT — Verified Behavior

## Schema
- `schema_def.json` is the authoritative schema source.
- Required fields: `id` (str), `value` (int or float).

## Validator
- Accepts records with correct required fields and types.
- Rejects records with wrong field types.
- Rejects records with missing required fields.
- Default mode (`strict=False`): accepts records with extra fields (e.g. `"fused": True`).
- Strict mode (`strict=True`): rejects records containing fields not defined in `schema_def.json`.

## Fusion
- Adds `"fused": True` to every output record.
- Preserves original field values unchanged.
- Preserves insertion order for unique ids.
- Accepts optional `strategy` flag (default: `"keep_first"`).
- `strategy="keep_first"`: for duplicate `"id"` values, first occurrence is kept and subsequent occurrences are dropped.
- `strategy="keep_last"`: for duplicate `"id"` values, last occurrence is kept and prior occurrences are dropped.
- Both strategies are deterministic.
- `"conflict": True` is added to the kept record when duplicate `"id"` values are encountered.
- `"conflict"` is absent when all ids are unique.
- Conflict flag does not affect selection logic; it is observational only.

## Dynamics
- Pass-through: returns records unchanged.

## Orchestrator
- Runs `fuse(records)` followed by `apply_dynamics(records)`.
- Validates each record before fusion; raises `ValueError` on first invalid record.
- Default mode (`strict=False`): allows extra fields through validation.
- Strict mode (`strict=True`): propagates to validator, rejects records with fields not defined in `schema_def.json`.
- `strategy` flag accepted (`"keep_first"` default, `"keep_last"` supported); passed directly to `fuse()`.
- Both strategies supported end-to-end through the full pipeline.
- **Strict input validation**: invalid values for `strategy`, `override_strategy`, or `preference_policy` raise `ValueError` before any execution.
  - `strategy` allowed values: `"keep_first"`, `"keep_last"`
  - `override_strategy` allowed values: `None`, `"keep_first"`, `"keep_last"`
  - `preference_policy` allowed values: `"keep_first"`, `"keep_last"`, `"prefer_consistent"`, `"prefer_lower_conflict"`
- `no_duplicates=False` (default): allows duplicate ids; fusion strategy determines which record is kept.
- `no_duplicates=True`: raises `ValueError` on first detected duplicate id; check occurs before fusion.
- `return_summary=False` (default): returns records only; return type unchanged.
- `return_summary=True`: returns `(records, summary)` where summary contains `input_count`, `output_count`, `duplicate_detected`, `strategies_differ`, `conflict_count`, `conflict_ids`, `conflict_map`, `evaluation_input`, `evaluation_snapshot`, `evaluation_triggered`, and (conditionally) `evaluation_result` and `evaluation_comparison`.
- `apply_preference=False` (default): behavior unchanged; output is the default pipeline result.
- `apply_preference=True`: requires `compare_strategies=True`, `return_summary=True`, and `enable_evaluation=True`; if `preferred_strategy` is not `None`, output switches to that strategy's result; otherwise default output is returned; no autonomous execution — explicit-only control.
- `override_strategy=None` (default): no effect; only applies when `apply_preference=True`; if set to `"keep_first"` or `"keep_last"`, it overrides `preferred_strategy` and that strategy's output is returned; explicit human control only, no automatic behavior.
- `preference_applied` is present in summary only when `apply_preference=True`; `True` when output was switched due to `preferred_strategy`; `False` when no switch occurs; purely observational audit signal.
- `execution_mode` is present in summary when `return_summary=True`; value is `"default"` (no `apply_preference`), `"preferred"` (`apply_preference=True` without override), or `"override"` (`override_strategy` used); purely observational, no behavior change.
- `strategies_differ` is `False` by default; equals `outputs_differ` from the comparison when `compare_strategies=True`.
- `conflict_count` is the number of output records containing `"conflict": True`; purely observational, does not affect pipeline behavior.
- `conflict_ids` is the list of `"id"` values from output records where `"conflict": True`, in output order; empty list when no conflicts exist; purely observational.
- `conflict_map` maps each conflicted id to its occurrence count in the input (e.g. `{"dup": 2}`); empty dict when no conflicts exist; purely structural and observational.
- `evaluation_input` is a structured dict containing `strategies_compared`, `outputs_differ`, `conflict_count`, and `conflict_ids` — all derived from existing signals; purely structural, no decision logic.
- `evaluation_snapshot` contains `input_records`, `output_records`, and `evaluation_input` — structural context only; performs no scoring, ranking, or selection.
- `evaluation_triggered` is `True` only when `enable_evaluation=True` and `return_summary=True`; `False` otherwise; purely a hook, no evaluation logic executes.
- `evaluation_result` is present only when `enable_evaluation=True` and `return_summary=True`; contains `status: "evaluated"`, `outputs_differ` (copied from `evaluation_input`), `conflict_count` (copied from summary), `consistency_check`, and `evaluation_details`; absent when `enable_evaluation=False`; no scoring, ranking, selection, learning, or self-modification occurs.
- `consistency_check` in `evaluation_result` is `True` when `evaluation_result.outputs_differ == evaluation_input.outputs_differ` AND `evaluation_result.conflict_count == summary.conflict_count`; otherwise `False`; compares existing values only, performs no ranking, selection, learning, or pipeline feedback.
- `evaluation_details` in `evaluation_result` contains `strategy_used` (string, copied from pipeline `strategy` parameter) and `compared` (boolean, same as `evaluation_input.strategies_compared`); purely observational, no decision logic.
- `evaluation_comparison` is present only when `compare_strategies=True`, `return_summary=True`, and `enable_evaluation=True`; contains `keep_first`, `keep_last`, `preferred_strategy`, `rationale`, `comparison_summary`, `difference_detail`, `divergence_detected`, and `losing_strategy_reason`; no selection, ranking, or pipeline feedback occurs.
- `divergence_detected` in `evaluation_comparison` is `True` when `keep_first_output != keep_last_output` (simple structural comparison); `False` when outputs are structurally identical; no behavior change, no decision logic.
- `losing_strategy_reason` in `evaluation_comparison` is `"keep_last not selected based on policy conditions"` when `preferred_strategy=="keep_first"`; `"keep_first not selected based on policy conditions"` when `preferred_strategy=="keep_last"`; `"no strategy selected due to no meaningful divergence"` when `preferred_strategy==None`; purely explanatory, no behavior change.
- `preference_strength` in `evaluation_comparison` is a deterministic symbolic signal derived from existing signals only: `"none"` when `preferred_strategy==None`; `"weak"` when `divergence_detected==False` but preferred is set; `"moderate"` when `divergence_detected==True` and conflict counts are equal; `"strong"` when `divergence_detected==True` and conflict counts differ. Current fusion model verifies `"none"` and `"moderate"` cases; `"weak"` and `"strong"` are structurally defined but not currently reachable under existing fusion behavior. No behavior change, no probabilistic scoring, no learning.
- `rationale` in `evaluation_comparison` is a string explaining why `preferred_strategy` was chosen, using only the `outputs_differ` signal; deterministic fixed wording; no new decision logic introduced.
- `comparison_summary` in `evaluation_comparison` is `"strategies produce different outputs"` when `outputs_differ==True`; `"strategies produce identical outputs"` when `outputs_differ==False`; purely descriptive, no decision logic.
- `difference_detail` in `evaluation_comparison` is `"outputs differ in at least one field"` when `outputs_differ==True`; `"no differences between outputs"` when `outputs_differ==False`; no field-level inspection, purely descriptive.
- `preferred_strategy` in `evaluation_comparison` is `"keep_first"` when `outputs_differ==True`; `None` when outputs are identical; deterministic fixed preference signal only; no automatic selection, feedback, or pipeline behavior change.
- `preference_policy="keep_first"` (default): sets the value of `preferred_strategy` when `outputs_differ==True`; supported values: `"keep_first"`, `"keep_last"`, `"prefer_consistent"`, `"prefer_lower_conflict"`; if `outputs_differ==False`, `preferred_strategy` remains `None`; does not execute unless `apply_preference=True`; deterministic, caller-configured, no autonomy.
- `compare_strategies=False` (default): behavior unchanged; returns records only.
- `compare_strategies=True`: runs both `keep_first` and `keep_last` on the same input; returns `(default_output, comparison_dict)`.
- Comparison dict contains only: `keep_first_output`, `keep_last_output`, `outputs_differ`.
- No arbitration, scoring, or learning occurs.
- `"prefer_lower_conflict"` policy selects the strategy with the lower `conflict_count` from `evaluation_comparison`; falls back to `"keep_first"` when conflict counts are equal. Under current fusion behavior, `keep_first` and `keep_last` produce equal `conflict_count` for the same duplicate-id set, so the fallback is always triggered in practice.
