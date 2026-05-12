"""
Deterministic fixed-step FCM execution layer.

Pure function: applied graph + initial activations + step count → replay record.
No convergence detection. No tolerance. No adaptive stopping.
No mutation. No learning. No persistence. No randomness.
"""
import hashlib
import json

from fcm_dynamics_preview import preview_fcm_dynamics, DynamicsPreviewError


class MultiStepError(ValueError):
    pass


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_fcm_steps(
    applied_graph: dict,
    initial_activations: dict,
    steps: int,
) -> dict:
    """
    Execute exactly `steps` FCM update steps using the frozen base contract.

    Each step calls preview_fcm_dynamics once. Step N+1 consumes the
    updated_activations from step N. steps=0 returns canonical initial
    activations unchanged with an empty step_results list.

    Args:
        applied_graph: must have status="applied"
        initial_activations: dict mapping node_id -> float in [-1.0, 1.0]
        steps: non-negative integer; exact number of steps to execute

    Returns:
        JSON-safe dict with run_id, steps_requested, initial_activations,
        final_activations, and ordered step_results.
        Inputs are not mutated.
    """
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
        raise MultiStepError(
            f"steps must be a non-negative integer, got {steps!r}"
        )
    if applied_graph.get("status") != "applied":
        raise MultiStepError(
            f"Graph status must be 'applied', got {applied_graph.get('status')!r}"
        )

    source_graph_id = applied_graph.get("graph_id", "")
    all_node_ids = sorted(n["node_id"] for n in applied_graph.get("nodes", []))

    # Validate and canonicalize initial activations (missing nodes → 0.0)
    for node_id, val in initial_activations.items():
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise MultiStepError(
                f"Activation for {node_id!r} must be numeric, got {type(val).__name__}"
            )
        if not (-1.0 <= float(val) <= 1.0):
            raise MultiStepError(
                f"Activation for {node_id!r} out of range [-1.0, 1.0]: {val}"
            )

    canonical_initial = {nid: 0.0 for nid in all_node_ids}
    for nid, val in initial_activations.items():
        if nid in canonical_initial:
            canonical_initial[nid] = float(val)

    step_results = []
    current = canonical_initial

    for step_num in range(1, steps + 1):
        result = preview_fcm_dynamics(applied_graph, current)
        step_results.append({
            "step": step_num,
            "preview_id": result["preview_id"],
            "input_activations": dict(current),
            "output_activations": dict(result["updated_activations"]),
        })
        current = result["updated_activations"]

    content_for_id = {
        "initial_activations": canonical_initial,
        "source_graph_id": source_graph_id,
        "step_results": step_results,
        "steps_requested": steps,
    }
    run_id = "fcm_run_" + _sha256(_canonical(content_for_id))[:24]

    return {
        "run_id": run_id,
        "steps_requested": steps,
        "initial_activations": canonical_initial,
        "final_activations": dict(current),
        "step_results": step_results,
    }
