import hashlib
import json
from pathlib import Path

from transcript_event import make_transcript_event, canonical_json
from transcript_topology import compute_transcript_linearization

FIXTURE_PATH = Path(__file__).parent / "artifacts" / "baselines" / "provenance_fixtures.json"

RUN_ID = "run_provenance_baseline"
TS_A = "2026-05-10T10:00:00+00:00"
TS_B = "2026-05-10T10:00:01+00:00"
TS_C = "2026-05-10T10:00:02+00:00"
GHOST_ID = "tmsg_ghost000000000000000000"
MISSING_REF_ID = "tmsg_missingref0000000000000"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _missing_refs(events: list) -> list:
    by_id = {e["message_id"] for e in events}
    missing = set()
    for e in events:
        for ref in e.get("references", []):
            if ref not in by_id:
                missing.add(ref)
    return sorted(missing)


def _build_clean_chain():
    p = make_transcript_event(
        run_id=RUN_ID, sender="agent_a", recipient="broadcast",
        role="proposal", content="Add causal edge: stress -> performance_drop",
        created_at=TS_A,
    )
    c = make_transcript_event(
        run_id=RUN_ID, sender="agent_b", recipient="agent_a",
        role="critique", content="Insufficient evidence for the proposed edge",
        created_at=TS_B,
        parent_message_id=p["message_id"],
        references=[p["message_id"]],
    )
    a = make_transcript_event(
        run_id=RUN_ID, sender="agent_arbiter", recipient="broadcast",
        role="arbiter", content="Proposal deferred. Critique accepted.",
        created_at=TS_C,
        parent_message_id=c["message_id"],
        references=[c["message_id"], p["message_id"]],
    )
    return [p, c, a]


def _build_orphaned_critique():
    p = make_transcript_event(
        run_id=RUN_ID, sender="agent_a", recipient="broadcast",
        role="proposal", content="Add causal edge: fatigue -> error_rate",
        created_at=TS_A,
    )
    c = make_transcript_event(
        run_id=RUN_ID, sender="agent_b", recipient="agent_a",
        role="critique", content="Parent message is missing from this exchange",
        created_at=TS_B,
        parent_message_id=GHOST_ID,
        references=[],
    )
    return [p, c]


def _build_broken_references():
    p = make_transcript_event(
        run_id=RUN_ID, sender="agent_a", recipient="broadcast",
        role="proposal", content="Add causal edge: workload -> burnout",
        created_at=TS_A,
    )
    c = make_transcript_event(
        run_id=RUN_ID, sender="agent_b", recipient="agent_a",
        role="critique", content="Edge weight unsubstantiated",
        created_at=TS_B,
        parent_message_id=p["message_id"],
        references=[p["message_id"]],
    )
    a = make_transcript_event(
        run_id=RUN_ID, sender="agent_arbiter", recipient="broadcast",
        role="arbiter", content="Arbiter references a missing message",
        created_at=TS_C,
        parent_message_id=c["message_id"],
        references=[c["message_id"], p["message_id"], MISSING_REF_ID],
    )
    return [p, c, a]


def _load_fixture():
    return json.loads(FIXTURE_PATH.read_text())


# 1. clean_chain produces zero orphaned and correct topology_order
def test_clean_chain_no_orphans():
    events = _build_clean_chain()
    result = compute_transcript_linearization(events)
    assert result["orphaned"] == []
    assert _missing_refs(events) == []
    assert len(result["order"]) == 3
    # Roles in order: proposal → critique → arbiter
    by_id = {e["message_id"]: e for e in events}
    roles = [by_id[mid]["role"] for mid in result["order"]]
    assert roles == ["proposal", "critique", "arbiter"]


# 2. orphaned_critique is detected in orphaned list
def test_orphaned_critique_detected():
    events = _build_orphaned_critique()
    result = compute_transcript_linearization(events)
    critique = events[1]
    assert critique["message_id"] in result["orphaned"]
    assert len(result["orphaned"]) == 1


# 3. broken_references arbiter still appears in topology_order
def test_broken_references_arbiter_in_order():
    events = _build_broken_references()
    result = compute_transcript_linearization(events)
    arbiter = events[2]
    assert arbiter["message_id"] in result["order"]
    assert result["orphaned"] == []
    missing = _missing_refs(events)
    assert MISSING_REF_ID in missing


# 4. topology_hash is byte-identical across repeated loads from artifact
def test_topology_hash_byte_identical_across_loads():
    hashes = set()
    for _ in range(5):
        fixture = _load_fixture()
        hashes.add(fixture["cases"]["clean_chain"]["topology_hash"])
        hashes.add(fixture["cases"]["orphaned_critique"]["topology_hash"])
        hashes.add(fixture["cases"]["broken_references"]["topology_hash"])
    assert len(hashes) == 3  # three distinct hashes, each stable


# 5. All three cases are deterministic across repeated programmatic generation
def test_all_cases_deterministic():
    def _generate():
        cases = {}
        for name, build in [
            ("clean_chain", _build_clean_chain),
            ("orphaned_critique", _build_orphaned_critique),
            ("broken_references", _build_broken_references),
        ]:
            events = build()
            lin = compute_transcript_linearization(events)
            cases[name] = {
                "topology_order": lin["order"],
                "orphaned": lin["orphaned"],
                "missing_references": _missing_refs(events),
                "topology_hash": lin["topology_hash"],
            }
        return _canon(cases)

    results = {_generate() for _ in range(5)}
    assert len(results) == 1


# 6. Artifact content matches programmatic regeneration exactly
def test_artifact_matches_programmatic_regeneration():
    fixture = _load_fixture()

    for name, build in [
        ("clean_chain", _build_clean_chain),
        ("orphaned_critique", _build_orphaned_critique),
        ("broken_references", _build_broken_references),
    ]:
        events = build()
        lin = compute_transcript_linearization(events)

        case = fixture["cases"][name]
        assert lin["order"] == case["topology_order"], f"{name}: topology_order mismatch"
        assert lin["orphaned"] == case["orphaned"], f"{name}: orphaned mismatch"
        assert _missing_refs(events) == case["missing_references"], f"{name}: missing_references mismatch"
        assert lin["topology_hash"] == case["topology_hash"], f"{name}: topology_hash mismatch"

        # topology_hash is sha256 of canonical(order)
        expected_hash = _sha256(_canon(lin["order"]))
        assert case["topology_hash"] == expected_hash, f"{name}: topology_hash does not match sha256(canonical(order))"
