import json
import pytest
from transcript_diff import diff_transcript_events
from transcript_event import make_transcript_event

RUN_ID = "run_diff_test"
TS_A = "2026-05-10T10:00:00+00:00"
TS_B = "2026-05-10T10:00:01+00:00"


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _proposal():
    return make_transcript_event(
        run_id=RUN_ID,
        sender="agent_a",
        recipient="agent_b",
        role="proposal",
        content="Add causal edge: stress -> performance_drop",
        created_at=TS_A,
    )


def _critique(parent_id):
    return make_transcript_event(
        run_id=RUN_ID,
        sender="agent_b",
        recipient="agent_a",
        role="critique",
        content="Insufficient evidence for the proposed edge",
        created_at=TS_B,
        parent_message_id=parent_id,
        references=[parent_id],
    )


# 1. Empty diff for identical inputs
def test_diff_identical_returns_empty():
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    events = [proposal, critique]
    result = diff_transcript_events(events, events)
    assert result["added"] == []
    assert result["removed"] == []
    assert len(result["unchanged"]) == 2
    assert result["added_ids"] == []
    assert result["removed_ids"] == []
    assert sorted(result["unchanged_ids"]) == sorted(
        [proposal["message_id"], critique["message_id"]]
    )


# 2. Added event is detected
def test_diff_detects_added_event():
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    result = diff_transcript_events([proposal], [proposal, critique])
    assert result["added_ids"] == [critique["message_id"]]
    assert result["removed_ids"] == []
    assert result["unchanged_ids"] == [proposal["message_id"]]
    assert result["added"][0]["message_id"] == critique["message_id"]


# 3. Removed event is detected
def test_diff_detects_removed_event():
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    result = diff_transcript_events([proposal, critique], [proposal])
    assert result["removed_ids"] == [critique["message_id"]]
    assert result["added_ids"] == []
    assert result["unchanged_ids"] == [proposal["message_id"]]
    assert result["removed"][0]["message_id"] == critique["message_id"]


# 4. Both added and removed in same diff
def test_diff_added_and_removed():
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    result = diff_transcript_events([proposal], [critique])
    assert proposal["message_id"] in result["removed_ids"]
    assert critique["message_id"] in result["added_ids"]
    assert result["unchanged_ids"] == []


# 5. Empty before and after
def test_diff_both_empty():
    result = diff_transcript_events([], [])
    assert result["added"] == []
    assert result["removed"] == []
    assert result["unchanged"] == []
    assert result["diff_id"].startswith("tdiff_")


# 6. diff_id is stable across repeated calls
def test_diff_id_is_stable():
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    r1 = diff_transcript_events([proposal], [proposal, critique])
    r2 = diff_transcript_events([proposal], [proposal, critique])
    assert r1["diff_id"] == r2["diff_id"]
    assert r1["diff_id"].startswith("tdiff_")


# 7. diff_id changes when inputs change
def test_diff_id_changes_with_content():
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    r1 = diff_transcript_events([proposal], [proposal, critique])
    r2 = diff_transcript_events([], [proposal, critique])
    assert r1["diff_id"] != r2["diff_id"]


# 8. Repeated calls are byte-identical
def test_diff_byte_identical():
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    results = [
        _canonical(diff_transcript_events([proposal], [proposal, critique]))
        for _ in range(5)
    ]
    assert len(set(results)) == 1


# 9. Input order does not affect diff result
def test_diff_order_independent():
    proposal = _proposal()
    critique = _critique(proposal["message_id"])
    r1 = diff_transcript_events([proposal, critique], [])
    r2 = diff_transcript_events([critique, proposal], [])
    assert _canonical(r1) == _canonical(r2)


# 10. diff_id format: "tdiff_" + 24 hex chars
def test_diff_id_format():
    result = diff_transcript_events([], [])
    assert result["diff_id"].startswith("tdiff_")
    hex_part = result["diff_id"][len("tdiff_"):]
    assert len(hex_part) == 24
    assert all(c in "0123456789abcdef" for c in hex_part)
