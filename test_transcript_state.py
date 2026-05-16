"""
Deterministic transcript-derived state reducer.
"""
import itertools
import json
import os
import tempfile
from pathlib import Path

from transcript_event import make_transcript_event
from transcript_state import TRANSCRIPT_EVENT_TYPE, reduce_transcript_state

_RUN = "test_ts_001"
_TS = {
    "p":  "2026-05-15T15:00:00+00:00",
    "ca": "2026-05-15T15:00:01+00:00",
    "cb": "2026-05-15T15:00:02+00:00",
    "ar": "2026-05-15T15:00:03+00:00",
}


def _make_exchange():
    proposal = make_transcript_event(
        run_id=_RUN, sender="agent_a", recipient="broadcast",
        role="proposal", content="Proposal: add edge X->Y", created_at=_TS["p"],
    )
    critique_a = make_transcript_event(
        run_id=_RUN, sender="agent_b", recipient="agent_a",
        role="critique", content="Critique A: insufficient evidence", created_at=_TS["ca"],
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    critique_b = make_transcript_event(
        run_id=_RUN, sender="agent_c", recipient="agent_a",
        role="critique", content="Critique B: alternative pathway", created_at=_TS["cb"],
        parent_message_id=proposal["message_id"],
        references=[proposal["message_id"]],
    )
    arbiter = make_transcript_event(
        run_id=_RUN, sender="agent_arbiter", recipient="broadcast",
        role="arbiter", content="Arbiter: both critiques accepted; proposal deferred",
        created_at=_TS["ar"],
        parent_message_id=critique_a["message_id"],
        references=[critique_a["message_id"], critique_b["message_id"], proposal["message_id"]],
    )
    return proposal, critique_a, critique_b, arbiter


# 1. Empty transcript returns canonical empty state
def test_empty_transcript_returns_canonical_empty_state():
    state = reduce_transcript_state([])
    assert state["message_count"]          == 0
    assert state["proposal_count"]         == 0
    assert state["critique_count"]         == 0
    assert state["arbiter_count"]          == 0
    assert state["participants"]           == []
    assert state["root_message_ids"]       == []
    assert state["unresolved_message_ids"] == []
    assert state["latest_role"]            is None
    assert state["latest_message_id"]      is None
    assert state["topology_edges"]         == []
    assert state["topology_order"]         == []
    json.dumps(state, sort_keys=True, separators=(",", ":"))  # must be JSON-safe


# 2. Critique loop derives expected counts and topology_order
def test_critique_loop_derives_expected_counts():
    proposal, critique_a, critique_b, arbiter = _make_exchange()
    state = reduce_transcript_state([proposal, critique_a, critique_b, arbiter])
    assert state["message_count"]  == 4
    assert state["proposal_count"] == 1
    assert state["critique_count"] == 2
    assert state["arbiter_count"]  == 1
    assert state["latest_role"]    == "arbiter"
    assert state["latest_message_id"]      == arbiter["message_id"]
    assert state["unresolved_message_ids"] == []
    assert state["root_message_ids"]       == [proposal["message_id"]]
    # topology_order must be the full linearized sequence ending at arbiter
    order = state["topology_order"]
    assert len(order) == 4
    assert order[0]   == proposal["message_id"]
    assert order[-1]  == arbiter["message_id"]


# 3. Participants sorted deterministically regardless of input order
def test_participants_sorted_deterministically():
    proposal, critique_a, critique_b, arbiter = _make_exchange()
    expected = sorted({"agent_a", "agent_b", "agent_c", "agent_arbiter"})
    state1 = reduce_transcript_state([proposal, critique_a, critique_b, arbiter])
    state2 = reduce_transcript_state([arbiter, critique_b, critique_a, proposal])
    assert state1["participants"] == expected
    assert state2["participants"] == expected


# 4. topology_edges parent-first and deterministic
def test_topology_edges_parent_first_and_deterministic():
    proposal, critique_a, critique_b, arbiter = _make_exchange()
    pid  = proposal["message_id"]
    caid = critique_a["message_id"]
    cbid = critique_b["message_id"]
    arid = arbiter["message_id"]

    state = reduce_transcript_state([proposal, critique_a, critique_b, arbiter])
    edges = state["topology_edges"]

    assert [pid, caid] in edges   # proposal → critique_a (parent + ref, deduped)
    assert [pid, cbid] in edges   # proposal → critique_b
    assert [caid, arid] in edges  # critique_a → arbiter (parent + ref, deduped)
    assert [cbid, arid] in edges  # critique_b → arbiter (ref)
    assert [pid,  arid] in edges  # proposal → arbiter (ref)
    assert len(edges) == 5

    # Edges are sorted — every [from, to] pair is in lexicographic order
    assert edges == sorted(edges)

    # Deterministic across permutations
    state2 = reduce_transcript_state([arbiter, critique_b, critique_a, proposal])
    assert state2["topology_edges"] == edges


# 5. Repeated reductions are byte-identical
def test_repeated_reductions_byte_identical():
    events = list(_make_exchange())
    ser = lambda s: json.dumps(s, sort_keys=True, separators=(",", ":"))
    s1 = ser(reduce_transcript_state(events))
    s2 = ser(reduce_transcript_state(events))
    s3 = ser(reduce_transcript_state(events))
    assert s1 == s2 == s3


# 6. Shuffled input converges to identical state
def test_shuffled_input_converges_to_same_state():
    events = list(_make_exchange())
    reference = reduce_transcript_state(events)
    for perm in itertools.permutations(events):
        assert reduce_transcript_state(list(perm)) == reference


# 7. Execution events are ignored
def test_execution_events_are_ignored():
    events = list(_make_exchange())
    non_transcript = [
        {"type": "candidate_validation", "input": {}, "output": {}},
        {"event_type": "system.heartbeat", "ts": "2026-05-15T00:00:00+00:00"},
    ]
    state_clean = reduce_transcript_state(events)
    state_mixed = reduce_transcript_state(events + non_transcript)
    assert state_clean == state_mixed
    assert state_mixed["message_count"] == 4


# 8. All existing tests still pass (regression)
def test_all_existing_tests_still_pass():
    from transcript_critique_loop import run_transcript_critique_loop
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    Path(path).unlink()
    result = run_transcript_critique_loop(Path(path))
    assert result["hash_chain_ok"] is True
    assert result["event_count"] == 4

    from bclaw4_state_engine import run_state_engine
    r = run_state_engine()
    assert r["chain_ok"] is True
    assert r["derived_state"]["critique_count"] == 2

    from transcript_topology import linearize_transcript_topology
    linearized = linearize_transcript_topology(list(_make_exchange()))
    assert linearized[0]["role"] == "proposal"
    assert linearized[-1]["role"] == "arbiter"
