import json
from pathlib import Path

from fcm_dynamics_preview import preview_fcm_dynamics


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _build_contribution_log(result: dict) -> dict:
    log = {}
    for edge in result["applied_edges"]:
        tgt = edge["target"]
        if tgt not in log:
            log[tgt] = []
        log[tgt].append({
            "source": edge["source"],
            "weight": edge["weight"],
            "activation": result["initial_activations"][edge["source"]],
            "contribution": edge["contribution"],
        })
    return log


def validate_replay(fixture_path) -> str:
    with open(fixture_path) as f:
        fixture = json.load(f)

    applied_graph = fixture["applied_graph"]
    initial_activations = fixture["initial_activations"]
    expected = fixture["expected"]

    result = preview_fcm_dynamics(applied_graph, initial_activations)

    for node_id, expected_val in expected["updated_activations"].items():
        actual_val = result["updated_activations"][node_id]
        assert abs(actual_val - expected_val) < 1e-9, (
            f"updated_activations[{node_id!r}]: expected {expected_val}, got {actual_val}"
        )

    actual_log = _build_contribution_log(result)
    for target, expected_contribs in expected["contribution_log"].items():
        assert target in actual_log, f"No contributions found for target {target!r}"
        actual_contribs = actual_log[target]
        assert len(actual_contribs) == len(expected_contribs), (
            f"Contribution count mismatch for {target!r}: "
            f"expected {len(expected_contribs)}, got {len(actual_contribs)}"
        )
        for i, (actual_c, expected_c) in enumerate(zip(actual_contribs, expected_contribs)):
            for field in ("source",):
                assert actual_c[field] == expected_c[field], (
                    f"contribution_log[{target!r}][{i}].{field}: "
                    f"expected {expected_c[field]!r}, got {actual_c[field]!r}"
                )
            for field in ("weight", "activation", "contribution"):
                assert abs(actual_c[field] - expected_c[field]) < 1e-9, (
                    f"contribution_log[{target!r}][{i}].{field}: "
                    f"expected {expected_c[field]}, got {actual_c[field]}"
                )

    preview_id_1 = result["preview_id"]
    result2 = preview_fcm_dynamics(applied_graph, initial_activations)
    assert result2["preview_id"] == preview_id_1, "preview_id not stable across runs"

    return preview_id_1
