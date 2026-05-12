# FCM Runtime Semantics v0.1

**Status:** frozen reference contract.
**Date:** 2026-05-12
**Supersedes:** `docs/FCM_SEMANTICS.md` (base preview contract — still valid at its layer)

This document freezes the full FCM runtime semantics: matrix construction,
synchronous update rule, intervention resolution, convergence criteria, canonical
hashing, and failure modes. All future layers must preserve this contract or declare
an explicit versioned migration.

---

## 1. Matrix Construction

The weight matrix `W` is derived from the applied graph's edge list.

**Definition:**

```
W[target][source] = edge.weight
```

- Rows index target nodes; columns index source nodes.
- All node IDs are sorted lexicographically before indexing. This sort is the only
  valid canonical order; insertion order, graph traversal order, and platform dict
  order are all invalid.
- If no edge exists from source to target, `W[target][source] = 0.0`.
- Edge weights must be in `[-1.0, 1.0]`. Weights outside this range are rejected at
  graph-apply time (`invalid_edge_weight`).
- Self-edges (`source == target`) are permitted and participate in accumulation like
  any other edge.
- Duplicate edge IDs within the same applied graph are rejected at graph-apply time.
- The matrix is read-only during propagation. Weight mutation during a step is
  invalid.

**Confidence scaling:**

The base runtime does not apply confidence scaling. The frozen formula uses raw
`edge.weight`. Layers that wish to scale by `edge.confidence` must do so before
constructing the applied graph, not inside the propagation step.

---

## 2. Update Semantics

### 2.1 Frozen formula

```
A(t+1)[i] = clamp(sum(W[i][j] * A(t)[j] for all j), -1.0, 1.0)
```

- **Synchronous:** all `A(t)[j]` values are read from the prior state before any
  `A(t+1)[i]` is written. In-step cascading is invalid.
- **Full replacement:** `A(t+1)[i]` replaces `A(t)[i]`. It is not additive
  (`A(t)[i] + delta`). The additive form used in `fcm_dynamics.py` and
  `fcm_propagation.py` is an earlier experimental variant and is **not canonical**
  under this contract.
- **No activation function:** the transfer function is the identity; clamping is the
  only nonlinearity. `tanh`, `sigmoid`, and other squashing functions are
  not part of v0.1.

### 2.2 Node persistence rule

A node with no incoming edges (no column in `W` that maps to it) preserves its
current activation exactly:

```
A(t+1)[i] = A(t)[i]   if sum(W[i][j] for all j) == 0.0 and no edges target i
```

This is equivalent to the frozen formula producing `clamp(0.0) = 0.0` only if the
prior activation was already `0.0`. For non-zero activations, the preservation rule
must be applied explicitly by checking `has_incoming[i]` before writing.

### 2.3 Missing activation semantics

A node present in the graph but absent from the initial activation dict defaults to
`0.0`. This is not the same as "preserve prior" and not the same as "undefined."
Missing-activation nodes participate in accumulation as `0.0`.

### 2.4 Damping

Damping (`d` in `[0.0, 1.0]`) scales the entire weight matrix uniformly:

```
A(t+1)[i] = clamp(sum(d * W[i][j] * A(t)[j] for all j), -1.0, 1.0)
```

Default damping is `1.0` (no scaling). Damping is applied before clamping.
Damping values outside `[0.0, 1.0]` are rejected as `invalid_damping`.

---

## 3. Activation Semantics

### 3.1 Domain

All node activations must be finite floats in `[-1.0, 1.0]`. Values outside this
range are rejected at validation time (`activation_out_of_range`). `NaN` and
`Inf` are always rejected.

### 3.2 Clamp

```python
clamp(value, lo=-1.0, hi=1.0) = max(lo, min(hi, value))
```

Clamping is applied after full accumulation, not to partial sums. Pre-clamping
intermediate contributions is invalid.

### 3.3 Precision

Internal accumulation uses Python `float` (IEEE 754 double). Contributions are
rounded to 15 significant decimal places before inclusion in the canonical output
record. The accumulated value before clamping is not rounded. The clamped result is
not rounded beyond float precision.

### 3.4 Semantic interpretation of the activation range

| Range | Interpretation |
|---|---|
| `+1.0` | Maximally present / active |
| `0.0` | Neutral / absent |
| `-1.0` | Maximally inhibited / inverse |

Values are continuous within `[-1.0, 1.0]`. The runtime assigns no categorical
meaning to threshold crossings.

---

## 4. Intervention Resolution Order

Interventions override the natural update formula for specific nodes at specific
steps. They are applied **after** accumulation and **before** the clamped result is
written to `A(t+1)`.

### 4.1 Intervention types

| Type | Effect |
|---|---|
| `impulse` | Adds a delta to the accumulated value before clamping: `accumulated + delta` |
| `permanent_shift` | Replaces the accumulated value with a fixed value: `fixed_value` |
| `clamp` | Forces the final value into a sub-range `[lo, hi]` ⊆ `[-1.0, 1.0]` |

### 4.2 Conflict rule: multiple types on the same node

When multiple intervention types target the same node at the same step, exactly one
wins according to this precedence order:

```
clamp  >  permanent_shift  >  impulse
```

The losing interventions are discarded silently for that step. They do not
accumulate, compound, or carry over.

### 4.3 Conflict rule: same type, same node

Multiple interventions of the **same type** on the **same node** at the **same
step** are **always invalid**, regardless of their values. The step is rejected with
`invalid_intervention` and no state update is written.

### 4.4 Resolution algorithm (per node per step)

```
1. Collect all interventions targeting node i at step t.
2. If more than one intervention shares the same type → raise invalid_intervention.
3. Select the highest-precedence type present.
4. Apply that intervention to the accumulated value.
5. Apply outer clamp to [-1.0, 1.0].
```

The outer clamp (step 5) is always applied, even after a `clamp` intervention. A
`clamp` intervention sub-range that violates `[-1.0, 1.0]` is rejected at
intervention construction time as `invalid_intervention_range`.

### 4.5 No-intervention path

If no intervention targets node `i` at step `t`, the frozen formula in §2.1 applies
without modification.

---

## 5. Oscillation and Convergence Semantics

### 5.1 No convergence detection in v0.1

The v0.1 runtime executes exactly the requested number of steps. It does not detect
fixed points, oscillation, or divergence and does not halt early.

Convergence detection, cycle detection, and adaptive stopping are deferred to a
future layer. Calling code that wants convergence behavior must implement its own
termination check on top of `run_fcm_steps`.

### 5.2 Fixed-point definition (informational)

A fixed point exists when:

```
A(t+1) == A(t)   for all nodes
```

Under linear accumulation with clamping, fixed points exist and are stable when the
spectral radius of `W` is less than 1. This is not enforced by the runtime.

### 5.3 Oscillation

Oscillation (period-2 or higher cycles) can occur when edge weights are large or
antagonistic. The runtime records all step results in `step_results`; callers can
detect oscillation by comparing `A(t)` and `A(t-k)` from the returned trajectory.

### 5.4 Trajectory record

`run_fcm_steps` returns a full ordered trajectory:

```json
{
  "step_results": [
    { "step": 1, "input_activations": {...}, "output_activations": {...}, "preview_id": "..." },
    ...
  ]
}
```

Each `preview_id` is content-addressed from the step's input and output, providing
an auditable hash chain over the trajectory.

---

## 6. Canonical Hashing

### 6.1 Serialization rule

All objects hashed for content-addressed IDs use the following canonical JSON form:

```python
json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

- `sort_keys=True`: key order is alphabetical, not insertion order.
- `separators=(",", ":")`: no spaces after `,` or `:`.
- `ensure_ascii=False`: unicode characters pass through unescaped.

Deviating from any of these settings produces a different hash and violates the
contract.

### 6.2 ID prefixes

| Object | Prefix | Hash source |
|---|---|---|
| Applied graph | `fcm_applied_` | `{applied_plan_ids, edges, nodes, source_snapshot_id}` |
| Dynamics preview | `fcm_preview_` | `{applied_edges, initial_activations, source_graph_id, updated_activations}` |
| Multi-step run | `fcm_run_` | `{initial_activations, source_graph_id, step_results, steps_requested}` |

All IDs use the first 24 hex characters of the SHA-256 digest of the canonical JSON.

### 6.3 PYTHONHASHSEED independence

All hashes must be identical regardless of `PYTHONHASHSEED`. This is guaranteed by
`sort_keys=True` in canonical serialization, which eliminates dict-iteration-order
dependence. Tests must verify this with at least seeds `{0, 1, 42, 12345, 99999}`.

### 6.4 Float serialization

Python's `json.dumps` serializes `float` values using Python's default float
representation. Contributions included in canonical output are rounded to 15
significant decimal places before serialization. The frozen clamped activation
values are serialized without additional rounding.

---

## 7. Failure Semantics

All errors are non-recoverable for the current call. No partial state is written.
Error types are raised as typed exceptions (`DynamicsPreviewError`, `MultiStepError`,
`GraphApplyError`) which are subclasses of `ValueError`.

| Code | Trigger | Layer |
|---|---|---|
| `invalid_status` | Graph `status != "applied"` passed to preview or multi-step | preview, multi-step |
| `activation_out_of_range` | Initial activation outside `[-1.0, 1.0]` | preview, multi-step |
| `activation_not_numeric` | Initial activation is non-numeric (including bool) | preview, multi-step |
| `invalid_edge_weight` | Edge weight outside `[-1.0, 1.0]` or non-numeric | preview |
| `invalid_snapshot_status` | Snapshot `status` not in `{"simulated", "baseline"}` | graph-apply |
| `invalid_plan` | Plan missing required fields (`plan_id`, `nodes`, `edges`) | graph-apply |
| `duplicate_plan_id` | Two plans share the same `plan_id` | graph-apply |
| `invalid_edge` | Edge missing `edge_id`, `source`, `target`, or `weight` | graph-apply |
| `invalid_steps` | `steps` is negative, non-integer, or bool | multi-step |
| `invalid_damping` | Damping outside `[0.0, 1.0]` | multi-step (future) |
| `invalid_intervention` | Same type, same node, same step | intervention layer (future) |
| `invalid_intervention_range` | Clamp sub-range violates `[-1.0, 1.0]` | intervention layer (future) |

Errors do not mutate input arguments. Input graphs, activation dicts, and plan lists
are identical before and after a failed call.

---

## 8. Reference Test Vectors

These vectors are frozen. Any change to the update rule, canonical serialization, or
clamping that produces a different result for these inputs is a breaking change.

### Vector 1: Basic one-step propagation

```
Graph:
  nodes: stress, fatigue, burnout
  edges: stress→burnout (w=0.7), fatigue→burnout (w=0.5)

Initial activations:
  stress=0.8, fatigue=0.6, burnout=0.0

Step 1:
  burnout_acc  = 0.8 * 0.7 + 0.6 * 0.5 = 0.56 + 0.30 = 0.86
  burnout_new  = clamp(0.86)  = 0.86
  stress_new   = 0.8  (no incoming edges — preserved)
  fatigue_new  = 0.6  (no incoming edges — preserved)

Output: {stress: 0.8, fatigue: 0.6, burnout: 0.86}
```

### Vector 2: Clamp ceiling

```
Graph:
  nodes: stress, fatigue, burnout
  edges: stress→burnout (w=0.7), fatigue→burnout (w=0.9)

Initial activations:
  stress=1.0, fatigue=1.0, burnout=0.0

Step 1:
  burnout_acc = 1.0 * 0.7 + 1.0 * 0.9 = 1.6
  burnout_new = clamp(1.6) = 1.0   ← clamped

Output: {stress: 1.0, fatigue: 1.0, burnout: 1.0}
```

### Vector 3: Clamp floor (negative weight)

```
Graph:
  nodes: stress, burnout
  edges: stress→burnout (w=-1.0)

Initial activations:
  stress=1.0, burnout=0.0

Step 1:
  burnout_acc = 1.0 * -1.0 = -1.0
  burnout_new = clamp(-1.0) = -1.0

Output: {stress: 1.0, burnout: -1.0}
```

### Vector 4: Zero-step returns initial unchanged

```
Graph: any valid applied graph
Initial activations: any valid dict
Steps: 0

Output:
  final_activations == canonicalized initial_activations
  step_results == []
```

### Vector 5: Missing activation defaults to 0.0

```
Graph:
  nodes: stress, fatigue, burnout
  edges: stress→burnout (w=0.7), fatigue→burnout (w=0.5)

Initial activations: {}  (empty)

Step 1:
  burnout_acc = 0.0 * 0.7 + 0.0 * 0.5 = 0.0
  burnout_new = clamp(0.0) = 0.0
  stress_new  = 0.0
  fatigue_new = 0.0

Output: {stress: 0.0, fatigue: 0.0, burnout: 0.0}
```

### Vector 6: Intervention — clamp beats impulse on same node

```
Node X: natural_acc = 0.3 (from propagation)
Interventions at step t:
  impulse(X, delta=0.6)         → would produce 0.9
  clamp(X, lo=0.0, hi=0.2)     → forces into [0.0, 0.2]

Resolution:
  clamp has higher precedence than impulse.
  impulse is discarded.
  clamp is applied: result = min(max(natural_acc, 0.0), 0.2) = 0.2
  outer clamp to [-1.0, 1.0]: 0.2 (unchanged)

Output: X = 0.2
```

### Vector 7: Same-type conflict is invalid

```
Node X: any accumulated value
Interventions at step t:
  impulse(X, delta=0.1)
  impulse(X, delta=0.2)   ← same type, same node, same step

Result: invalid_intervention raised, no state written.
```

---

## Implementation Contradictions Found

The following divergences between this document and the current implementation are
noted. They are not bugs in the preview/multi-step layer (which is correct) but are
present in earlier experimental files:

1. **`fcm_dynamics.py` `apply_fcm_step`** — uses additive form
   `clamp(old.activation + incoming[node_id])` instead of the frozen replacement
   form `clamp(sum(W[i][j] * A(t)[j]))`. This file also multiplies by
   `edge.confidence * damping` inside accumulation, which is not part of the v0.1
   canonical formula.

2. **`fcm_propagation.py` `compute_next_activations`** — uses additive form
   `clamp(current[node_id] + influence)`. Also assumes a `GraphState` object with
   `.incoming_edges()` rather than the dict-based applied graph contract.

Neither file is exercised by the canonical test suite (`test_fcm_dynamics_preview.py`,
`test_fcm_multi_step.py`). Both are superseded by `fcm_dynamics_preview.py` and
`fcm_multi_step.py`, which correctly implement the frozen formula.
