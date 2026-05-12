import json
from pathlib import Path

from tests.golden_replays.golden_replay_validator import validate_replay
from fcm_dynamics_preview import preview_fcm_dynamics

FIXTURE_DIR = Path(__file__).parent / "golden_replays"


def test_replay_001_single_edge_positive():
    preview_id = validate_replay(FIXTURE_DIR / "replay_001_single_edge_positive.json")
    assert preview_id.startswith("fcm_preview_")


def test_replay_002_multi_parent_accumulation():
    validate_replay(FIXTURE_DIR / "replay_002_multi_parent_accumulation.json")


def test_replay_003_clamp_saturation():
    validate_replay(FIXTURE_DIR / "replay_003_clamp_saturation.json")


def test_replay_004_persistence_disconnected():
    validate_replay(FIXTURE_DIR / "replay_004_persistence_disconnected.json")


def test_replay_005_missing_activation_zero():
    validate_replay(FIXTURE_DIR / "replay_005_missing_activation_zero.json")


def test_replay_006_ordering_invariance():
    with open(FIXTURE_DIR / "replay_006_ordering_invariance.json") as f:
        fixture = json.load(f)

    # Validate canonical edge order via standard validator
    pid_canonical = validate_replay(FIXTURE_DIR / "replay_006_ordering_invariance.json")

    # Run alternate insertion order directly
    initial = fixture["initial_activations"]
    r_alt = preview_fcm_dynamics(fixture["applied_graph_alt"], initial)

    assert r_alt["preview_id"] == pid_canonical, (
        f"preview_id differs under alternate edge order: "
        f"{r_alt['preview_id']!r} != {pid_canonical!r}"
    )
    assert r_alt["updated_activations"] == fixture["expected"]["updated_activations"], (
        "updated_activations differ under alternate edge order"
    )

    r_canonical = preview_fcm_dynamics(fixture["applied_graph"], initial)
    assert r_alt["applied_edges"] == r_canonical["applied_edges"], (
        "contribution ordering differs under alternate edge order"
    )


def test_replay_007_serialize_deserialize_replay():
    with open(FIXTURE_DIR / "replay_007_serialize_deserialize_replay.json") as f:
        fixture = json.load(f)

    # Validate canonical run
    pid = validate_replay(FIXTURE_DIR / "replay_007_serialize_deserialize_replay.json")

    # JSON round-trip the graph and activations, then re-run
    graph_rt = json.loads(json.dumps(fixture["applied_graph"]))
    initial_rt = json.loads(json.dumps(fixture["initial_activations"]))
    r_rt = preview_fcm_dynamics(graph_rt, initial_rt)

    assert r_rt["preview_id"] == pid, (
        f"preview_id changed after JSON round-trip: {r_rt['preview_id']!r} != {pid!r}"
    )
    assert r_rt["updated_activations"] == fixture["expected"]["updated_activations"], (
        "updated_activations changed after JSON round-trip"
    )
