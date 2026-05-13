import itertools
import json
import pytest

from transcript_event import make_transcript_event
from transcript_topology import compute_transcript_linearization, TranscriptLinearizationError

RUN_ID = "run_lin_test"
TS_A = "2026-05-10T10:00:00+00:00"
TS_B = "2026-05-10T10:00:01+00:00"
TS_C = "2026-05-10T10:00:02+00:00"
TS_D = "2026-05-10T10:00:03+00:00"


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _make_chain():
    proposal = make_transcript_event(
        run_id=RUN_ID, sender="agent_a", recipient="broadcast",
        role="proposal", content="Proposal: add edge X->Y", created_at=TS_A,
    )
    critique = make_transcript_event(
        run_id=RUN_ID, sender="agent_b", recipient="agent_a",
        role="critique", content="Critique: insufficient evidence",
        created_at=TS_B,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    arbiter = make_transcript_event(
        run_id=RUN_ID, sender="agent_arbiter", recipient="broadcast",
        role="arbiter", content="Arbiter: proposal deferred",
        created_at=TS_C,
        parent_message_id=critique["message_id"],
        references=[critique["message_id"], proposal["message_id"]],
    )
    return proposal, critique, arbiter


# 1. Empty event set returns well-formed result
def test_empty_events_returns_well_formed():
    result = compute_transcript_linearization([])
    assert result["order"] == []
    assert result["node_count"] == 0
    assert result["orphaned"] == []
    assert result["linearization_id"].startswith("tlin_")
    assert len(result["linearization_id"]) == len("tlin_") + 24


# 2. linearization_id format: "tlin_" + 24 hex chars
def test_linearization_id_format():
    proposal, critique, arbiter = _make_chain()
    result = compute_transcript_linearization([proposal, critique, arbiter])
    assert result["linearization_id"].startswith("tlin_")
    hex_part = result["linearization_id"][len("tlin_"):]
    assert len(hex_part) == 24
    assert all(c in "0123456789abcdef" for c in hex_part)


# 3. Order is deterministic across all permutations
def test_linearization_order_deterministic_across_permutations():
    proposal, critique, arbiter = _make_chain()
    events = [proposal, critique, arbiter]
    ref = compute_transcript_linearization(events)["order"]
    for perm in itertools.permutations(events):
        result = compute_transcript_linearization(list(perm))
        assert result["order"] == ref


# 4. linearization_id is stable across repeated calls
def test_linearization_id_stable():
    proposal, critique, arbiter = _make_chain()
    events = [proposal, critique, arbiter]
    r1 = compute_transcript_linearization(events)
    r2 = compute_transcript_linearization(events)
    assert r1["linearization_id"] == r2["linearization_id"]


# 5. linearization_id changes when event set changes
def test_linearization_id_changes_with_events():
    proposal, critique, arbiter = _make_chain()
    r1 = compute_transcript_linearization([proposal, critique])
    r2 = compute_transcript_linearization([proposal, critique, arbiter])
    assert r1["linearization_id"] != r2["linearization_id"]


# 6. Entire result is byte-identical across repeated calls
def test_result_byte_identical():
    proposal, critique, arbiter = _make_chain()
    events = [proposal, critique, arbiter]
    results = [_canonical(compute_transcript_linearization(events)) for _ in range(5)]
    assert len(set(results)) == 1


# 7. Proposal precedes critique precedes arbiter
def test_causal_order_preserved():
    proposal, critique, arbiter = _make_chain()
    result = compute_transcript_linearization([proposal, critique, arbiter])
    order = result["order"]
    assert order.index(proposal["message_id"]) < order.index(critique["message_id"])
    assert order.index(critique["message_id"]) < order.index(arbiter["message_id"])


# 8. node_count matches input length
def test_node_count_matches_input():
    proposal, critique, arbiter = _make_chain()
    result = compute_transcript_linearization([proposal, critique, arbiter])
    assert result["node_count"] == 3


# 9. Orphaned events (parent not in set) reported in orphaned list
def test_orphaned_event_detected():
    proposal, critique, _ = _make_chain()
    # critique references proposal, but proposal is absent
    result = compute_transcript_linearization([critique])
    assert critique["message_id"] in result["orphaned"]


# 10. Cycle raises TranscriptLinearizationError
def test_cycle_raises_error():
    mid_a = "tmsg_cycleaaaaaaaaaaaaaaaaaaa"
    mid_b = "tmsg_cyclebbbbbbbbbbbbbbbbbb"
    event_a = {
        "event_type": "transcript.message",
        "message_id": mid_a,
        "run_id": RUN_ID,
        "sender": "agent_a",
        "recipient": "broadcast",
        "role": "proposal",
        "content": "A references B",
        "references": [mid_b],
        "parent_message_id": None,
        "created_at": TS_A,
        "metadata": {},
    }
    event_b = {
        "event_type": "transcript.message",
        "message_id": mid_b,
        "run_id": RUN_ID,
        "sender": "agent_b",
        "recipient": "broadcast",
        "role": "critique",
        "content": "B references A",
        "references": [mid_a],
        "parent_message_id": None,
        "created_at": TS_B,
        "metadata": {},
    }
    with pytest.raises(TranscriptLinearizationError, match="Cycle detected"):
        compute_transcript_linearization([event_a, event_b])


# 11. topology_hash matches sha256 of canonical(order)
def test_topology_hash_matches_order():
    import hashlib
    proposal, critique, arbiter = _make_chain()
    result = compute_transcript_linearization([proposal, critique, arbiter])
    expected = hashlib.sha256(
        _canonical(result["order"]).encode("utf-8")
    ).hexdigest()
    assert result["topology_hash"] == expected


# 12. Single-event linearization
def test_single_event_linearization():
    proposal = make_transcript_event(
        run_id=RUN_ID, sender="agent_a", recipient="broadcast",
        role="proposal", content="Solo proposal", created_at=TS_A,
    )
    result = compute_transcript_linearization([proposal])
    assert result["order"] == [proposal["message_id"]]
    assert result["node_count"] == 1
    assert result["orphaned"] == []
