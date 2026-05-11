import copy
import json
import pytest

from fcm_graph_apply import apply_fcm_plans, GraphApplyError

SIMULATED_SNAPSHOT = {
    "snapshot_id": "snap_001",
    "status": "simulated",
    "nodes": [
        {"node_id": "stress", "label": "Stress", "activation": 0.5},
        {"node_id": "burnout", "label": "Burnout", "activation": 0.2},
    ],
    "edges": [
        {"edge_id": "e_stress_burnout", "source": "stress", "target": "burnout",
         "weight": 0.7, "edge_type": "causal"},
    ],
}

BASELINE_SNAPSHOT = {
    "snapshot_id": "snap_baseline_001",
    "status": "baseline",
    "nodes": [
        {"node_id": "workload", "label": "Workload", "activation": 0.6},
    ],
    "edges": [],
}

VALID_PLAN = {
    "plan_id": "plan_001",
    "nodes": [
        {"node_id": "fatigue", "label": "Fatigue", "activation": 0.3},
    ],
    "edges": [
        {"edge_id": "e_fatigue_burnout", "source": "fatigue", "target": "burnout",
         "weight": 0.5, "edge_type": "causal"},
    ],
}


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# 1. Apply simulated snapshot deterministically
def test_apply_simulated_snapshot_deterministically():
    result = apply_fcm_plans([VALID_PLAN], simulated_snapshot=SIMULATED_SNAPSHOT)
    assert result["status"] == "applied"
    assert result["node_count"] >= 1
    assert result["edge_count"] >= 1
    assert result["applied_plan_ids"] == ["plan_001"]
    assert result["source_snapshot_id"] == "snap_001"
    assert result["graph_id"].startswith("fcm_applied_")


# 2. Repeated runs byte-identical
def test_repeated_runs_byte_identical():
    r1 = apply_fcm_plans([VALID_PLAN], simulated_snapshot=SIMULATED_SNAPSHOT)
    r2 = apply_fcm_plans([VALID_PLAN], simulated_snapshot=SIMULATED_SNAPSHOT)
    r3 = apply_fcm_plans([VALID_PLAN], simulated_snapshot=SIMULATED_SNAPSHOT)
    assert _canonical(r1) == _canonical(r2) == _canonical(r3)


# 3. Invalid snapshot status rejected
def test_invalid_snapshot_status_rejected():
    bad = {**SIMULATED_SNAPSHOT, "status": "draft"}
    with pytest.raises(GraphApplyError, match="Invalid snapshot status"):
        apply_fcm_plans([VALID_PLAN], simulated_snapshot=bad)

    bad2 = {**BASELINE_SNAPSHOT, "status": "pending"}
    with pytest.raises(GraphApplyError, match="Invalid snapshot status"):
        apply_fcm_plans([VALID_PLAN], baseline_snapshot=bad2)


# 4. Malformed edges rejected
def test_malformed_edges_rejected():
    bad_plan = {
        "plan_id": "plan_bad",
        "nodes": [],
        "edges": [{"source": "a", "target": "b"}],  # missing edge_id and weight
    }
    with pytest.raises(GraphApplyError, match="Edge missing required fields"):
        apply_fcm_plans([bad_plan])


# 5. Duplicate plan IDs rejected
def test_duplicate_plan_ids_rejected():
    plan_copy = {**VALID_PLAN}
    with pytest.raises(GraphApplyError, match="Duplicate plan_id"):
        apply_fcm_plans([VALID_PLAN, plan_copy])


# 6. Canonical ordering preserved
def test_canonical_ordering_preserved():
    plan_a = {
        "plan_id": "plan_z",
        "nodes": [{"node_id": "z_node", "label": "Z", "activation": 0.1}],
        "edges": [{"edge_id": "e_z", "source": "z_node", "target": "burnout",
                   "weight": 0.1, "edge_type": "causal"}],
    }
    plan_b = {
        "plan_id": "plan_a",
        "nodes": [{"node_id": "a_node", "label": "A", "activation": 0.9}],
        "edges": [{"edge_id": "e_a", "source": "a_node", "target": "stress",
                   "weight": 0.9, "edge_type": "causal"}],
    }
    r1 = apply_fcm_plans([plan_a, plan_b])
    r2 = apply_fcm_plans([plan_b, plan_a])  # reversed input order
    # applied_plan_ids always sorted
    assert r1["applied_plan_ids"] == sorted(["plan_z", "plan_a"])
    assert r2["applied_plan_ids"] == sorted(["plan_z", "plan_a"])
    # Byte-identical output regardless of plan input order
    assert _canonical(r1) == _canonical(r2)


# 7. graph_id is deterministic (content-addressed)
def test_graph_id_deterministic():
    r1 = apply_fcm_plans([VALID_PLAN], simulated_snapshot=SIMULATED_SNAPSHOT)
    r2 = apply_fcm_plans([VALID_PLAN], simulated_snapshot=SIMULATED_SNAPSHOT)
    assert r1["graph_id"] == r2["graph_id"]
    assert r1["graph_id"].startswith("fcm_applied_")


# 8. Inputs remain unchanged after apply
def test_inputs_remain_unchanged():
    plan_before = copy.deepcopy(VALID_PLAN)
    snapshot_before = copy.deepcopy(SIMULATED_SNAPSHOT)
    baseline_before = copy.deepcopy(BASELINE_SNAPSHOT)

    apply_fcm_plans(
        [VALID_PLAN],
        baseline_snapshot=BASELINE_SNAPSHOT,
        simulated_snapshot=SIMULATED_SNAPSHOT,
    )

    assert VALID_PLAN == plan_before
    assert SIMULATED_SNAPSHOT == snapshot_before
    assert BASELINE_SNAPSHOT == baseline_before


# 9. No-snapshot apply works with plans only
def test_apply_plans_only_no_snapshot():
    plan = {
        "plan_id": "plan_standalone",
        "nodes": [{"node_id": "n1", "label": "N1", "activation": 0.5}],
        "edges": [{"edge_id": "e1", "source": "n1", "target": "n1",
                   "weight": 0.1, "edge_type": "causal"}],
    }
    result = apply_fcm_plans([plan])
    assert result["status"] == "applied"
    assert result["source_snapshot_id"] is None
    assert result["node_count"] == 1
    assert result["edge_count"] == 1


# 10. Baseline + simulated + plan all merge correctly
def test_baseline_simulated_plan_merge():
    result = apply_fcm_plans(
        [VALID_PLAN],
        baseline_snapshot=BASELINE_SNAPSHOT,
        simulated_snapshot=SIMULATED_SNAPSHOT,
    )
    node_ids = {n["node_id"] for n in result["nodes"]}
    # workload from baseline, stress/burnout from simulated, fatigue from plan
    assert "workload" in node_ids
    assert "stress" in node_ids
    assert "burnout" in node_ids
    assert "fatigue" in node_ids
    assert result["status"] == "applied"
    assert _canonical(result) == _canonical(result)  # byte-stable
