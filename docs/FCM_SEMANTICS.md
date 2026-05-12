# FCM Semantics Contract v1.0

Status: canonical base-layer contract.

This document freezes the deterministic FCM preview semantics. Future dynamics, governance, arbitration, and learning layers must preserve this contract unless an explicit migration is made.

## 1. Update model

The FCM preview uses synchronous single-step update.

Each node computes its next activation only from prior-state activations. No in-place cascading is allowed within a step.

## 2. Activation domain

All node activations must be numeric values in `[-1.0, 1.0]`.

## 3. Propagation rule

For each target node, compute the weighted sum of incoming contributions:

`next[target] = clamp(sum(initial[source] * weight[source,target]), -1.0, 1.0)`

Clamping occurs after full accumulation. Pre-clamping partial contributions is not valid under this contract.

## 4. Node persistence

Nodes with no incoming edges remain unchanged.

## 5. Missing activation semantics

A missing source activation is treated as `0.0`.

Missing activation does not mean preserve-prior and does not mean undefined.

## 6. Canonical ordering

Contribution ordering must be deterministic and auditable.

Incoming contributions for each target must be ordered canonically before accumulation and serialization. Future changes must not rely on incidental Python dict order, graph traversal order, or platform-specific iteration behavior.

## 7. Determinism and replay

The same applied graph and same initial activations must produce the same updated activations, contribution list, and preview hash.

Preview behavior must be side-effect free.

## 8. Mutation rules

Preview execution must not mutate:

- input graph
- edge weights
- node identities
- initial activation input

Only returned preview state may describe updated activations.

## 9. Deferred non-goals

The base contract does not define:

- nonlinear activations
- multi-step convergence
- adaptive weights
- stochastic updates
- temporal decay
- governance rules
- learning rules
- agent or arbitration behavior

Those layers may be added later only on top of this frozen base.
