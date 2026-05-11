import copy
import json
import pytest

from fcm_dynamics_preview import preview_fcm_dynamics, DynamicsPreviewError

APPLIED_GRAPH = {
    "graph_id": "fcm_applied_test001",
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

INITIAL = {"stress": 0.8, "fatigue": 0.6, "burnout": 0.0}


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# 1. Computes one-step activation update correctly
def test_computes_one_step_activation_update():
    result = preview_fcm_dynamics(APPLIED_GRAPH, INITIAL)
    assert result["status"] == "preview"
    # burnout = clamp(0.8 * 0.7 + 0.6 * 0.5) = clamp(0.56 + 0.30) = clamp(0.86)
    assert abs(result["updated_activations"]["burnout"] - 0.86) < 1e-9
    # stress and fatigue have no incoming edges — preserved
    assert result["updated_activations"]["stress"] == 0.8
    assert result["updated_activations"]["fatigue"] == 0.6


# 2. Clamps high/low values deterministically
def test_clamps_high_and_low_values():
    graph = {
        **APPLIED_GRAPH,
        "edges": [
            {"edge_id": "e_high", "source": "stress", "target": "burnout",
             "weight": 1.0, "edge_type": "causal"},
        ],
    }
    result = preview_fcm_dynamics(graph, {"stress": 1.0, "fatigue": 0.0, "burnout": 0.0})
    assert result["updated_activations"]["burnout"] == 1.0

    graph_neg = {
        **APPLIED_GRAPH,
        "edges": [
            {"edge_id": "e_low", "source": "stress", "target": "burnout",
             "weight": -1.0, "edge_type": "causal"},
        ],
    }
    result2 = preview_fcm_dynamics(graph_neg, {"stress": 1.0, "fatigue": 0.0, "burnout": 0.0})
    assert result2["updated_activations"]["burnout"] == -1.0

    graph_over = {
        **APPLIED_GRAPH,
        "edges": [
            {"edge_id": "e1", "source": "stress", "target": "burnout", "weight": 0.7},
            {"edge_id": "e2", "source": "fatigue", "target": "burnout", "weight": 0.9},
        ],
    }
    result3 = preview_fcm_dynamics(graph_over, {"stress": 1.0, "fatigue": 1.0, "burnout": 0.0})
    assert result3["updated_activations"]["burnout"] == 1.0  # clamped from 1.6


# 3. Missing node activations default to 0.0
def test_missing_activations_default_to_zero():
    result = preview_fcm_dynamics(APPLIED_GRAPH, {})
    assert result["initial_activations"]["stress"] == 0.0
    assert result["initial_activations"]["fatigue"] == 0.0
    assert result["initial_activations"]["burnout"] == 0.0
    assert result["updated_activations"]["burnout"] == 0.0


# 4. Rejects non-applied graph status
def test_rejects_non_applied_graph_status():
    for bad_status in ("simulated", "baseline", "draft", None):
        bad = {**APPLIED_GRAPH, "status": bad_status}
        with pytest.raises(DynamicsPreviewError, match="Graph status must be 'applied'"):
            preview_fcm_dynamics(bad, INITIAL)


# 5. Rejects invalid activation values
def test_rejects_invalid_activation_values():
    with pytest.raises(DynamicsPreviewError, match="out of range"):
        preview_fcm_dynamics(APPLIED_GRAPH, {"stress": 1.5, "fatigue": 0.0, "burnout": 0.0})
    with pytest.raises(DynamicsPreviewError, match="out of range"):
        preview_fcm_dynamics(APPLIED_GRAPH, {"stress": -1.1, "fatigue": 0.0, "burnout": 0.0})
    with pytest.raises(DynamicsPreviewError, match="must be numeric"):
        preview_fcm_dynamics(APPLIED_GRAPH, {"stress": "high", "fatigue": 0.0, "burnout": 0.0})


# 6. Stable ordering across shuffled inputs
def test_stable_ordering_across_shuffled_inputs():
    shuffled_activations = {"burnout": 0.0, "fatigue": 0.6, "stress": 0.8}
    r1 = preview_fcm_dynamics(APPLIED_GRAPH, INITIAL)
    r2 = preview_fcm_dynamics(APPLIED_GRAPH, shuffled_activations)
    assert _canonical(r1) == _canonical(r2)


# 7. preview_id is deterministic (content-addressed)
def test_preview_id_deterministic():
    r1 = preview_fcm_dynamics(APPLIED_GRAPH, INITIAL)
    r2 = preview_fcm_dynamics(APPLIED_GRAPH, INITIAL)
    assert r1["preview_id"] == r2["preview_id"]
    assert r1["preview_id"].startswith("fcm_preview_")


# 8. Repeated runs byte-identical
def test_repeated_runs_byte_identical():
    outputs = [_canonical(preview_fcm_dynamics(APPLIED_GRAPH, INITIAL)) for _ in range(5)]
    assert len(set(outputs)) == 1


# 9. Inputs remain unchanged after preview
def test_inputs_remain_unchanged():
    graph_before = copy.deepcopy(APPLIED_GRAPH)
    activations_before = copy.deepcopy(INITIAL)
    preview_fcm_dynamics(APPLIED_GRAPH, INITIAL)
    assert APPLIED_GRAPH == graph_before
    assert INITIAL == activations_before
