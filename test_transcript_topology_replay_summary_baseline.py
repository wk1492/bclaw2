import json
import tempfile
from pathlib import Path

from transcript_critique_loop import run_transcript_critique_loop
from transcript_ledger import replay_transcript_events, replay_transcript_topology
from transcript_topology import compute_transcript_linearization

ARTIFACT = (
    Path(__file__).parent
    / "artifacts/baselines/transcript_topology_replay_summary_c38284a.json"
)

FROZEN = json.loads(ARTIFACT.read_text())

TOPOLOGY_HASH = FROZEN["topology_hash"]
LINEARIZATION_ID = FROZEN["linearization_id"]
LINEARIZED_ORDER = FROZEN["linearized_order"]
EVENT_COUNT = FROZEN["event_count"]
ROLE_SEQUENCE = FROZEN["role_sequence"]


def _run_topology():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ledger.jsonl"
        run_transcript_critique_loop(path)
        events = replay_transcript_events(path)
        topo = replay_transcript_topology(path)
        lin = compute_transcript_linearization(events)
    return topo, lin, events


# 1. Frozen topology_hash matches live computation
def test_topology_hash_frozen():
    topo, _, _ = _run_topology()
    assert topo["topology_hash"] == TOPOLOGY_HASH


# 2. Frozen linearized_order matches live computation
def test_linearized_order_frozen():
    topo, _, _ = _run_topology()
    assert topo["order"] == LINEARIZED_ORDER


# 3. Frozen linearization_id matches live compute_transcript_linearization
def test_linearization_id_frozen():
    _, lin, _ = _run_topology()
    assert lin["linearization_id"] == LINEARIZATION_ID


# 4. event_count matches frozen value
def test_event_count_frozen():
    topo, _, _ = _run_topology()
    assert topo["node_count"] == EVENT_COUNT


# 5. orphaned list is empty
def test_orphaned_empty():
    topo, _, _ = _run_topology()
    assert topo["orphaned"] == []


# 6. role_sequence in linearized order matches frozen value
def test_role_sequence_frozen():
    topo, _, events = _run_topology()
    by_id = {e["message_id"]: e for e in events}
    roles = [by_id[mid]["role"] for mid in topo["order"]]
    assert roles == ROLE_SEQUENCE


# 7. Shuffled input produces identical topology_hash (input-order independence)
def test_shuffled_input_identical_topology_hash():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ledger.jsonl"
        run_transcript_critique_loop(path)
        events = replay_transcript_events(path)

    shuffled = list(reversed(events))
    lin_forward = compute_transcript_linearization(events)
    lin_reversed = compute_transcript_linearization(shuffled)
    assert lin_forward["topology_hash"] == lin_reversed["topology_hash"]
    assert lin_forward["order"] == lin_reversed["order"]


# 8. Repeated independent runs produce identical topology_hash
def test_repeated_runs_identical_topology_hash():
    topo_a, _, _ = _run_topology()
    topo_b, _, _ = _run_topology()
    assert topo_a["topology_hash"] == topo_b["topology_hash"]


# 9. replay_transcript_topology and compute_transcript_linearization agree on order
def test_topology_and_linearization_order_agree():
    topo, lin, _ = _run_topology()
    assert topo["order"] == lin["order"]
    assert topo["topology_hash"] == lin["topology_hash"]


# 10. Artifact file is present and parses cleanly
def test_artifact_file_readable():
    assert ARTIFACT.exists()
    data = json.loads(ARTIFACT.read_text())
    for key in ("topology_hash", "linearization_id", "linearized_order",
                "event_count", "orphaned", "role_sequence"):
        assert key in data
