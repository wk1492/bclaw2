import itertools
import json
from pathlib import Path

from ledger_writer import LedgerWriter, verify_ledger
from transcript_event import canonical_json, make_transcript_event
from transcript_ledger import replay_execution_events
from transcript_topology import (
    compute_transcript_linearization,
    linearize_transcript,
    linearize_transcript_topology,
)
from transcript_validator import reconstruct_thread

RUN_ID = "run_topology_001"
TS_A = "2026-05-10T14:00:00+00:00"
TS_B = "2026-05-10T14:00:01+00:00"
TS_C = "2026-05-10T14:00:02+00:00"
TS_D = "2026-05-10T14:00:03+00:00"


def _make_four_event_exchange():
    proposal = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_a",
        recipient="broadcast",
        role="proposal",
        content="Proposal: add edge X->Y",
        created_at=TS_A,
    )
    critique_a = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_b",
        recipient="agent_a",
        role="critique",
        content="Critique A: insufficient evidence",
        created_at=TS_B,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    critique_b = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_c",
        recipient="agent_a",
        role="critique",
        content="Critique B: alternative pathway preferred",
        created_at=TS_C,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    arbiter = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_arbiter",
        recipient="broadcast",
        role="arbiter",
        content="Arbiter: proposal deferred",
        created_at=TS_D,
        parent_message_id=critique_a["message_id"],
        references=[
            critique_a["message_id"],
            critique_b["message_id"],
            proposal["message_id"],
        ],
    )
    return proposal, critique_a, critique_b, arbiter


def _ids(events):
    return [event["message_id"] for event in events]


def _serialized(events):
    return canonical_json([event["message_id"] for event in events])


# 1. Stable traversal despite shuffled append order.
def test_linearization_independent_of_insertion_order():
    events = list(_make_four_event_exchange())
    reference = _ids(linearize_transcript(events))

    for permutation in itertools.permutations(events):
        result = _ids(linearize_transcript(list(permutation)))
        assert result == reference


# 2. Deterministic ordering for sibling critiques.
def test_sibling_ordering_uses_created_at_then_message_id():
    proposal = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_a",
        recipient="broadcast",
        role="proposal",
        content="Proposal",
        created_at=TS_A,
    )

    critique_x = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_x",
        recipient="agent_a",
        role="critique",
        content="Critique X",
        created_at=TS_B,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )

    critique_y = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_y",
        recipient="agent_a",
        role="critique",
        content="Critique Y",
        created_at=TS_B,
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )

    result = _ids(linearize_transcript([proposal, critique_y, critique_x]))
    expected = sorted([critique_x["message_id"], critique_y["message_id"]])

    assert result[0] == proposal["message_id"]
    assert result[1:] == expected


# 3. Orphan handling deterministic (synthetic roots).
def test_orphaned_parent_becomes_synthetic_root():
    orphan = make_transcript_event(
        run_id=RUN_ID,
        sender="agent_orphan",
        recipient="broadcast",
        role="system",
        content="Orphaned transcript",
        created_at="2026-05-10T13:59:59+00:00",
        parent_message_id="missing_parent_message",
    )

    proposal, critique_a, critique_b, arbiter = _make_four_event_exchange()
    result = linearize_transcript([
        critique_b,
        arbiter,
        orphan,
        proposal,
        critique_a,
    ])

    ids = _ids(result)
    assert ids[0] == orphan["message_id"]
    assert proposal["message_id"] in ids

    report = compute_transcript_linearization(result)
    assert report["orphaned"] == [orphan["message_id"]]


# 4. Mixed ledger filtering.
def test_non_transcript_events_ignored():
    proposal, critique_a, critique_b, arbiter = _make_four_event_exchange()
    mixed = [
        {"event_type": "execution.record", "id": "exec_001"},
        proposal,
        critique_a,
        {"event_type": "candidate.validation", "id": "exec_002"},
        critique_b,
        arbiter,
    ]

    linearized = linearize_transcript(mixed)
    assert len(linearized) == 4
    assert all(event["event_type"] == "transcript.message" for event in linearized)


# 5. Repeated traversal byte-identical.
def test_repeated_linearization_byte_identical():
    events = list(_make_four_event_exchange())

    out1 = _serialized(linearize_transcript(events))
    out2 = _serialized(linearize_transcript(events))
    out3 = _serialized(linearize_transcript(list(reversed(events))))

    assert out1 == out2 == out3


# 6. Canonical serialization preserved.
def test_canonical_serialization_preserved():
    events = list(_make_four_event_exchange())
    linearized = linearize_transcript(events)

    serialized = canonical_json([
        {"message_id": event["message_id"], "role": event["role"]}
        for event in linearized
    ])

    parsed = json.loads(serialized)
    assert parsed[0]["role"] == "proposal"
    assert parsed[-1]["role"] == "arbiter"


# 7. Existing transcript replay proof compatibility.
def test_replay_proof_compatibility_preserved():
    proposal = make_transcript_event(
        run_id="run_proof",
        sender="agent_a",
        recipient="agent_b",
        role="proposal",
        content="Add causal edge: fatigue -> error_rate",
        created_at="2026-05-10T11:00:00+00:00",
    )

    critique = make_transcript_event(
        run_id="run_proof",
        sender="agent_b",
        recipient="agent_a",
        role="critique",
        content="Edge weight unsubstantiated",
        created_at="2026-05-10T11:00:01+00:00",
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )

    arbiter = make_transcript_event(
        run_id="run_proof",
        sender="agent_arbiter",
        recipient="broadcast",
        role="arbiter",
        content="Proposal deferred pending evidence",
        created_at="2026-05-10T11:00:02+00:00",
        parent_message_id=critique["message_id"],
        references=[critique["message_id"], proposal["message_id"]],
    )

    replay = reconstruct_thread([proposal, critique, arbiter])
    topology = linearize_transcript_topology([arbiter, proposal, critique])

    assert [event["role"] for event in replay] == ["proposal", "critique", "arbiter"]
    assert [event["role"] for event in topology] == ["proposal", "critique", "arbiter"]


# 8. Hash-chain verification still passes on mixed ledgers.
def test_hash_chain_verification_passes_on_mixed_ledger(tmp_path):
    path = Path(tmp_path) / "mixed_topology_ledger.jsonl"
    writer = LedgerWriter(path)

    writer.append({
        "event_type": "execution.record",
        "value": 1,
        "payload": {"kind": "execution"},
    })

    proposal, critique_a, critique_b, arbiter = _make_four_event_exchange()

    for event in [proposal, critique_a, critique_b, arbiter]:
        writer.append(dict(event))

    linearized = linearize_transcript([
        {"event_type": "execution.record", "value": 2},
        proposal,
        arbiter,
        critique_b,
        critique_a,
    ])

    assert [event["role"] for event in linearized] == [
        "proposal",
        "critique",
        "critique",
        "arbiter",
    ]

    execution_only = replay_execution_events(path)
    assert len(execution_only) == 1
    assert execution_only[0]["event_type"] == "execution.record"

    verification = verify_ledger(path)
    assert verification["ok"] is True
    assert verification["failures"] == []
