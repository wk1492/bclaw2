import copy
import json

import pytest

from fcm_dynamics_preview import preview_fcm_dynamics
from fcm_multi_step import run_fcm_steps, MultiStepError


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _make_graph():
    return {
        "graph_id": "fcm_applied_test_multi",
        "status": "applied",
        "nodes": [
            {"node_id": "stress", "label": "Stress", "activation": 0.0},
            {"node_id": "fatigue", "label": "Fatigue", "activation": 0.0},
            {"node_id": "burnout", "label": "Burnout", "activation": 0.0},
        ],
        "edges": [
            {"edge_id": "e1", "source": "stress", "target": "burnout",
             "weight": 0.7, "edge_type": "causal"},
            {"edge_id": "e2", "source": "fatigue", "target": "burnout",
             "weight": 0.5, "edge_type": "causal"},
        ],
        "applied_plan_ids": ["plan_001"],
        "source_snapshot_id": "snap_001",
        "node_count": 3,
        "edge_count": 2,
    }


def _make_initial():
    return {"stress": 0.8, "fatigue": 0.6, "burnout": 0.0}


# 1. Zero-step returns canonical initial activations, empty step_results
def test_zero_step_returns_initial_unchanged():
    graph = _make_graph()
    initial = _make_initial()
    result = run_fcm_steps(graph, initial, steps=0)
    assert result["steps_requested"] == 0
    assert result["step_results"] == []
    assert result["final_activations"]["stress"] == 0.8
    assert result["final_activations"]["fatigue"] == 0.6
    assert result["final_activations"]["burnout"] == 0.0
    assert result["initial_activations"] == result["final_activations"]


# 2. Single-step matches preview_fcm_dynamics directly
def test_single_step_matches_preview_fcm_dynamics():
    graph = _make_graph()
    initial = _make_initial()
    result = run_fcm_steps(graph, initial, steps=1)
    preview = preview_fcm_dynamics(graph, initial)
    assert result["final_activations"] == preview["updated_activations"]
    assert result["step_results"][0]["preview_id"] == preview["preview_id"]


# 2. Two-step propagation feeds step-1 output into step-2
def test_two_step_propagation():
    graph = _make_graph()
    initial = _make_initial()
    result = run_fcm_steps(graph, initial, steps=2)
    assert result["steps_requested"] == 2
    assert len(result["step_results"]) == 2

    step1_out = result["step_results"][0]["output_activations"]
    step2_in = result["step_results"][1]["input_activations"]
    assert step1_out == step2_in

    step2_out = result["step_results"][1]["output_activations"]
    assert result["final_activations"] == step2_out


# 3. Multi-step chain: each step input == previous step output
def test_multi_step_chain_continuity():
    graph = _make_graph()
    initial = _make_initial()
    result = run_fcm_steps(graph, initial, steps=5)
    assert len(result["step_results"]) == 5
    for i in range(1, 5):
        prev_out = result["step_results"][i - 1]["output_activations"]
        curr_in = result["step_results"][i]["input_activations"]
        assert prev_out == curr_in, f"Step {i} input != step {i-1} output"


# 4. Clamp behavior across fixed steps
def test_clamp_behavior_across_steps():
    graph = {
        **_make_graph(),
        "edges": [
            {"edge_id": "e1", "source": "stress", "target": "burnout",
             "weight": 1.0, "edge_type": "causal"},
            {"edge_id": "e2", "source": "fatigue", "target": "burnout",
             "weight": 1.0, "edge_type": "causal"},
        ],
    }
    initial = {"stress": 1.0, "fatigue": 1.0, "burnout": 0.0}
    result = run_fcm_steps(graph, initial, steps=3)
    for step in result["step_results"]:
        burnout = step["output_activations"]["burnout"]
        assert burnout == 1.0, f"burnout should be clamped to 1.0, got {burnout}"


# 5. Deterministic replay stability — identical inputs produce identical output
def test_deterministic_replay_stability():
    graph = _make_graph()
    initial = _make_initial()
    results = [_canonical(run_fcm_steps(graph, initial, steps=3)) for _ in range(5)]
    assert len(set(results)) == 1


# 6. Immutable history — inputs not mutated
def test_inputs_not_mutated():
    graph = _make_graph()
    initial = _make_initial()
    graph_before = copy.deepcopy(graph)
    initial_before = copy.deepcopy(initial)
    run_fcm_steps(graph, initial, steps=4)
    assert graph == graph_before
    assert initial == initial_before


# 6b. step_results records are independent snapshots (no aliasing)
def test_step_results_are_independent_snapshots():
    graph = _make_graph()
    initial = _make_initial()
    result = run_fcm_steps(graph, initial, steps=3)
    snapshots = [s["input_activations"] for s in result["step_results"]]
    for i, snap in enumerate(snapshots):
        for j, other in enumerate(snapshots):
            if i != j:
                assert snap is not other


# 7. Invalid step count rejected
def test_invalid_step_count_rejected():
    graph = _make_graph()
    initial = _make_initial()
    with pytest.raises(MultiStepError):
        run_fcm_steps(graph, initial, steps=-1)
    with pytest.raises(MultiStepError):
        run_fcm_steps(graph, initial, steps=1.5)
    with pytest.raises(MultiStepError):
        run_fcm_steps(graph, initial, steps=True)


# 8. Non-applied graph rejected
def test_non_applied_graph_rejected():
    graph = {**_make_graph(), "status": "simulated"}
    initial = _make_initial()
    with pytest.raises(MultiStepError, match="Graph status must be 'applied'"):
        run_fcm_steps(graph, initial, steps=1)


# 9. run_id is content-addressed and stable
def test_run_id_deterministic():
    graph = _make_graph()
    initial = _make_initial()
    r1 = run_fcm_steps(graph, initial, steps=2)
    r2 = run_fcm_steps(graph, initial, steps=2)
    assert r1["run_id"] == r2["run_id"]
    assert r1["run_id"].startswith("fcm_run_")
