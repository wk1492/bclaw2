import itertools
import json

from transcript_event import make_transcript_event
from transcript_topology import (
    TRANSCRIPT_EVENT_TYPE,
    compute_transcript_linearization,
    linearize_transcript_topology,
)

RUN_ID = "run_topology_001"
TS_A = "2026-05-10T14:00:00+00:00"
TS_B = "2026-05-10T14:00:01+00:00"
TS_C = "2026-05-10T14:00:02+00:00"
TS_D = "2026-05-10T14:00:03+00:00"


def _make_four_event_exchange():
    proposal = make_transcript_event(
        run_id=RUN_ID, sender="agent_a", recipient="broadcast",
        role="proposal", content="Proposal: add edge X->Y", created_at=TS_A,
    )
    critique_a = make_transcript_event(
        run_id=RUN_ID, sender="agent_b", recipient="agent_a",
        role="critique", content="Critique A: insufficient evidence",
        created_at=TS_B,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    critique_b = make_transcript_event(
        run_id=RUN_ID, sender="agent_c", recipient="agent_a",
        role="critique", content="Critique B: alternative pathway preferred",
        created_at=TS_C,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    arbiter = make_transcript_event(
        run_id=RUN_ID, sender="agent_arbiter", recipient="broadcast",
        role="arbiter", content="Arbiter: proposal deferred",
        created_at=TS_D,
        parent_message_id=critique_a["message_id"],
        references=[critique_a["message_id"], critique_b["message_id"], proposal["message_id"]],
    )
    return proposal, critique_a, critique_b, arbiter


def _ids(linearized):
    return [e["message_id"] for e in linearized]


def _serialize(linearized):
    return json.dumps(
        [e["message_id"] for e in linearized],
        sort_keys=True, separators=(",", ":"),
    )


# 1. Insertion order permutations produce identical linearization
def test_linearization_independent_of_insertion_order():
    events = list(_make_four_event_exchange())
    reference = _ids(linearize_transcript_topology(events))

    for perm in itertools.permutations(events):
        result = _ids(linearize_transcript_topology(list(perm)))
        assert result == reference, f"Permutation produced different order: {result}"


# 2. Sibling tie-breaking deterministic (critiques are siblings under proposal)
def test_sibling_tie_breaking_deterministic():
    proposal, critique_a, critique_b, arbiter = _make_four_event_exchange()
    events = [proposal, critique_a, critique_b, arbiter]

    r1 = _ids(linearize_transcript_topology(events))
    r2 = _ids(linearize_transcript_topology(list(reversed(events))))
    assert r1 == r2

    # Siblings ordered by (created_at, message_id): critique_a (TS_B) before critique_b (TS_C)
    assert r1.index(critique_a["message_id"]) < r1.index(critique_b["message_id"])


# 3. Arbiter always appears after critiques it references
def test_arbiter_always_after_referenced_critiques():
    proposal, critique_a, critique_b, arbiter = _make_four_event_exchange()
    for perm in itertools.permutations([proposal, critique_a, critique_b, arbiter]):
        result = _ids(linearize_transcript_topology(list(perm)))
        arb_pos = result.index(arbiter["message_id"])
        assert result.index(critique_a["message_id"]) < arb_pos
        assert result.index(critique_b["message_id"]) < arb_pos
        assert result.index(proposal["message_id"]) < arb_pos


# 4. Disconnected nodes handled deterministically
def test_disconnected_nodes_handled_deterministically():
    proposal, critique_a, critique_b, arbiter = _make_four_event_exchange()
    orphan = make_transcript_event(
        run_id=RUN_ID, sender="agent_x", recipient="broadcast",
        role="system", content="Unrelated system note",
        created_at="2026-05-10T13:59:59+00:00",
    )
    events = [proposal, critique_a, critique_b, arbiter, orphan]
    r1 = _ids(linearize_transcript_topology(events))
    r2 = _ids(linearize_transcript_topology(list(reversed(events))))
    assert r1 == r2
    # Orphan has no deps and earliest timestamp — should appear first
    assert r1[0] == orphan["message_id"]


# 5. Repeated runs byte-identical
def test_repeated_runs_byte_identical():
    events = list(_make_four_event_exchange())
    out1 = _serialize(linearize_transcript_topology(events))
    out2 = _serialize(linearize_transcript_topology(events))
    out3 = _serialize(linearize_transcript_topology(list(reversed(events))))
    assert out1 == out2 == out3


# 6. Canonical serialization preserved
def test_canonical_serialization_preserved():
    events = list(_make_four_event_exchange())
    linearized = linearize_transcript_topology(events)
    serialized = json.dumps(
        [{"message_id": e["message_id"], "role": e["role"]} for e in linearized],
        sort_keys=True, separators=(",", ":"),
    )
    parsed = json.loads(serialized)
    assert len(parsed) == 4
    assert parsed[0]["role"] == "proposal"
    assert parsed[-1]["role"] == "arbiter"


# --- Explicit contract assertions ---

# Root is always index 0
def test_root_proposal_is_index_zero():
    proposal, critique_a, critique_b, arbiter = _make_four_event_exchange()
    for perm in itertools.permutations([proposal, critique_a, critique_b, arbiter]):
        result = linearize_transcript_topology(list(perm))
        assert result[0]["message_id"] == proposal["message_id"], \
            f"Expected proposal at index 0, got {result[0]['role']}"


# Every parent appears before every child
def test_every_parent_before_child():
    proposal, critique_a, critique_b, arbiter = _make_four_event_exchange()
    for perm in itertools.permutations([proposal, critique_a, critique_b, arbiter]):
        result = linearize_transcript_topology(list(perm))
        ids = _ids(result)
        for event in result:
            parent_id = event.get("parent_message_id")
            if parent_id and parent_id in ids:
                assert ids.index(parent_id) < ids.index(event["message_id"]), \
                    f"Parent {parent_id} must precede child {event['message_id']}"


# Every referenced message appears before the referencing message
def test_every_reference_before_referencing_event():
    proposal, critique_a, critique_b, arbiter = _make_four_event_exchange()
    for perm in itertools.permutations([proposal, critique_a, critique_b, arbiter]):
        result = linearize_transcript_topology(list(perm))
        ids = _ids(result)
        for event in result:
            for ref_id in event.get("references", []):
                if ref_id in ids:
                    assert ids.index(ref_id) < ids.index(event["message_id"]), \
                        f"Reference {ref_id} must precede {event['message_id']}"


# message_id tie-break when siblings share identical timestamp
def test_sibling_message_id_tiebreak_when_same_timestamp():
    proposal = make_transcript_event(
        run_id=RUN_ID, sender="agent_a", recipient="broadcast",
        role="proposal", content="Proposal", created_at=TS_A,
    )
    # Two critiques at identical timestamp — ordered by message_id
    crit_x = make_transcript_event(
        run_id=RUN_ID, sender="agent_x", recipient="agent_a",
        role="critique", content="Critique X",
        created_at=TS_B,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    crit_y = make_transcript_event(
        run_id=RUN_ID, sender="agent_y", recipient="agent_a",
        role="critique", content="Critique Y",
        created_at=TS_B,  # same timestamp as crit_x
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    events = [proposal, crit_x, crit_y]
    for perm in itertools.permutations(events):
        result = _ids(linearize_transcript_topology(list(perm)))
        # Both orderings with same timestamp must agree — tie-broken by message_id lexicographically
        expected_order = sorted(
            [crit_x["message_id"], crit_y["message_id"]]
        )
        actual_order = [mid for mid in result if mid != proposal["message_id"]]
        assert actual_order == expected_order, \
            f"Same-timestamp siblings must be ordered by message_id: {actual_order}"


# 5. Orphan reference is reported, not inferred
def test_orphan_parent_reported_not_inferred():
    """
    An event whose parent_message_id does not exist in the event set is an orphan.
    The orphaned event is listed in result["orphaned"]; no phantom parent node is created.
    The orphan still appears in result["order"] (placed by timestamp tie-break, not suppressed).
    """
    proposal = make_transcript_event(
        run_id=RUN_ID, sender="agent_a", recipient="broadcast",
        role="proposal", content="Proposal", created_at=TS_A,
    )
    dangling_parent = "tmsg_" + "0" * 24  # valid-looking but absent from event set
    orphan_critique = make_transcript_event(
        run_id=RUN_ID, sender="agent_b", recipient="agent_a",
        role="critique", content="Critique with missing parent",
        created_at=TS_B,
        parent_message_id=dangling_parent,
    )

    result = compute_transcript_linearization([proposal, orphan_critique])

    # Orphan event reported in orphaned list — its parent is missing
    assert orphan_critique["message_id"] in result["orphaned"], (
        "Event with nonexistent parent_message_id must appear in orphaned list"
    )
    # Missing parent NOT inferred — node_count reflects real events only
    assert result["node_count"] == 2
    # Both real events appear in order
    assert len(result["order"]) == 2
    assert proposal["message_id"] in result["order"]
    assert orphan_critique["message_id"] in result["order"]
    # Phantom node is NOT created for the dangling parent
    assert dangling_parent not in result["order"]
    # Topology hash is a 64-char hex string (stable)
    assert len(result["topology_hash"]) == 64


# 8. Non-transcript execution events are ignored
def test_non_transcript_events_are_ignored():
    """
    Execution ledger events and other records with event_type != 'transcript.message'
    are silently excluded from linearization. They do not appear in the output,
    do not affect ordering, and do not change the topology of transcript events.
    """
    proposal, critique_a, critique_b, arbiter = _make_four_event_exchange()

    # A typical execution ledger record — no event_type field, uses 'type'
    execution_record = {
        "type": "candidate_validation",
        "timestamp": TS_A,
        "input": {"x": 1},
        "output": {"y": 2},
        "metadata": {},
    }
    # A record with an explicit non-transcript event_type
    system_record = {
        "event_type": "system.heartbeat",
        "message_id": "hb_001",
        "timestamp": TS_A,
    }

    mixed = [proposal, execution_record, critique_a, system_record, critique_b, arbiter]
    transcript_only = [proposal, critique_a, critique_b, arbiter]

    result_mixed = linearize_transcript_topology(mixed)
    result_clean = linearize_transcript_topology(transcript_only)

    # Output is identical with or without non-transcript events in input
    assert _ids(result_mixed) == _ids(result_clean), (
        "Non-transcript events must not alter linearization output"
    )
    # Exactly 4 transcript events, not 6
    assert len(result_mixed) == 4
    # All output events are transcript.message
    assert all(e.get("event_type") == TRANSCRIPT_EVENT_TYPE for e in result_mixed)


# 7. Replay proof topology unaffected by linearizer existence
def test_replay_proof_topology_unaffected():
    from transcript_event import make_transcript_event
    from transcript_validator import reconstruct_thread

    prop = make_transcript_event(
        run_id="run_proof", sender="agent_a", recipient="agent_b",
        role="proposal", content="Add causal edge: fatigue -> error_rate",
        created_at="2026-05-10T11:00:00+00:00",
    )
    crit = make_transcript_event(
        run_id="run_proof", sender="agent_b", recipient="agent_a",
        role="critique", content="Edge weight unsubstantiated; evidence threshold not met",
        created_at="2026-05-10T11:00:01+00:00",
        parent_message_id=prop["message_id"],
        references=[prop["message_id"]],
    )
    arb = make_transcript_event(
        run_id="run_proof", sender="agent_arbiter", recipient="broadcast",
        role="arbiter", content="Proposal deferred pending evidence. Critique accepted.",
        created_at="2026-05-10T11:00:02+00:00",
        parent_message_id=crit["message_id"],
        references=[crit["message_id"], prop["message_id"]],
    )
    thread = reconstruct_thread([prop, crit, arb])
    assert [e["role"] for e in thread] == ["proposal", "critique", "arbiter"]

    linearized = linearize_transcript_topology([prop, crit, arb])
    assert [e["role"] for e in linearized] == ["proposal", "critique", "arbiter"]
