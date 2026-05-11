import itertools
import json

from transcript_event import make_transcript_event
from transcript_topology import linearize_transcript_topology

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
