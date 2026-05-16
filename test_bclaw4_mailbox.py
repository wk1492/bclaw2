"""
BCLAW4 Experiment 002 — deterministic agent mailbox protocol.
Branch: bclaw4-chaos-lab-001.
"""
import json
import os
import tempfile
from pathlib import Path

from bclaw4_mailbox import Mailbox, RUN_ID


def _fresh_mailbox():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    Path(path).unlink()

    mb = Mailbox(path)
    m1 = mb.append_message(
        "agent_a", "agent_b", "proposal",
        "Proposal: add causal edge fatigue->error_rate",
    )
    m2 = mb.append_message(
        "agent_b", "agent_a", "critique",
        "Critique: insufficient evidence for edge weight",
        references=[m1["message_id"]],
    )
    m3 = mb.append_message(
        "agent_a", "broadcast", "proposal",
        "Open proposal: fatigue->error_rate pending arbiter review",
    )
    m4 = mb.append_message(
        "agent_b", "arbiter", "critique",
        "Escalate: unresolved dispute on edge weight",
        references=[m1["message_id"], m2["message_id"]],
    )
    m5 = mb.append_message(
        "arbiter", "broadcast", "arbiter",
        "Resolution: defer pending evidence; critique accepted",
        references=[m1["message_id"], m2["message_id"], m4["message_id"]],
    )
    return mb, path, (m1, m2, m3, m4, m5)


# 1. agent_a can send to agent_b
def test_agent_a_sends_to_agent_b():
    mb, _, (m1, *_) = _fresh_mailbox()
    inbox_ids = [e["message_id"] for e in mb.read_mailbox("agent_b")]
    assert m1["message_id"] in inbox_ids, "agent_b inbox must contain proposal sent by agent_a"


# 2. agent_b reads only its addressed messages (not those addressed to others)
def test_agent_b_reads_only_addressed_and_broadcasts():
    mb, _, (m1, m2, m3, m4, m5) = _fresh_mailbox()
    agent_b_inbox = {e["message_id"] for e in mb.read_mailbox("agent_b")}
    broadcasts = {e["message_id"] for e in mb.read_broadcasts()}

    assert m1["message_id"] in agent_b_inbox           # addressed to agent_b
    assert m2["message_id"] not in agent_b_inbox        # sent by agent_b, not addressed to it
    assert m4["message_id"] not in agent_b_inbox        # addressed to arbiter
    assert m3["message_id"] in broadcasts               # broadcast from agent_a
    assert m5["message_id"] in broadcasts               # broadcast from arbiter


# 3. arbiter reads critiques addressed to arbiter
def test_arbiter_reads_critique_addressed_to_arbiter():
    mb, _, (m1, m2, m3, m4, m5) = _fresh_mailbox()
    arbiter_inbox_ids = [e["message_id"] for e in mb.read_mailbox("arbiter")]
    assert m4["message_id"] in arbiter_inbox_ids, "arbiter inbox must contain critique sent to arbiter"
    assert m5["message_id"] not in arbiter_inbox_ids, "arbiter's own broadcast must not appear in its inbox"


# 4. broadcast is visible via read_broadcasts, not in individual agent mailboxes
def test_broadcast_visible_to_all_via_read_broadcasts():
    mb, _, (m1, m2, m3, m4, m5) = _fresh_mailbox()
    broadcasts = {e["message_id"] for e in mb.read_broadcasts()}
    assert m3["message_id"] in broadcasts
    assert m5["message_id"] in broadcasts

    for agent in ("agent_a", "agent_b", "arbiter"):
        inbox = {e["message_id"] for e in mb.read_mailbox(agent)}
        assert m3["message_id"] not in inbox, f"broadcast m3 must not appear in {agent} mailbox"
        assert m5["message_id"] not in inbox, f"broadcast m5 must not appear in {agent} mailbox"


# 5. mailbox order is deterministic by (created_at, message_id)
def test_mailbox_order_deterministic_by_created_at_then_message_id():
    mb, _, _ = _fresh_mailbox()
    mb.append_message("agent_b", "agent_a", "reply", "Follow-up to critique")
    mb.append_message("arbiter", "agent_a", "system", "System note: review requested")

    inbox = mb.read_mailbox("agent_a")
    sort_keys = [(e.get("created_at", ""), e["message_id"]) for e in inbox]
    assert sort_keys == sorted(sort_keys), (
        "read_mailbox must return events sorted by (created_at, message_id)"
    )


# 6. repeated reads are byte-identical
def test_repeated_reads_byte_identical():
    mb, _, _ = _fresh_mailbox()

    def _ids(events):
        return json.dumps(
            [e["message_id"] for e in events],
            sort_keys=True, separators=(",", ":"),
        )

    assert _ids(mb.read_mailbox("agent_b")) == _ids(mb.read_mailbox("agent_b"))
    assert _ids(mb.read_broadcasts()) == _ids(mb.read_broadcasts())
    assert _ids(mb.reconstruct_conversation()) == _ids(mb.reconstruct_conversation())


# 7. replay from ledger reconstructs identical mailboxes
def test_replay_from_ledger_reconstructs_identical_mailboxes():
    mb, path, _ = _fresh_mailbox()
    original = [e["message_id"] for e in mb.read_mailbox("agent_b")]

    mb2 = Mailbox(path)
    replayed = [e["message_id"] for e in mb2.read_mailbox("agent_b")]

    assert replayed == original, "fresh Mailbox from same ledger must reconstruct identical mailbox"


# 8. hash-chain verification passes after all appends
def test_hash_chain_verification_passes():
    mb, _, _ = _fresh_mailbox()
    s = mb.summary()
    assert s["chain_ok"] is True, f"chain verification failed: {s}"
    assert s["message_count"] == 5


# 9. execution replay ignores mailbox transcript events
def test_execution_replay_ignores_mailbox_transcript_events():
    from transcript_ledger import replay_execution_events
    mb, path, _ = _fresh_mailbox()
    assert replay_execution_events(path) == [], (
        "execution replay must return [] — all mailbox events are transcript.message type"
    )


# 10. no mailbox state exists outside ledger replay
def test_no_mailbox_state_outside_ledger_replay():
    mb, path, _ = _fresh_mailbox()
    original = mb.summary()
    del mb

    mb_fresh = Mailbox(path)
    replayed = mb_fresh.summary()

    assert replayed["message_count"] == original["message_count"]
    assert replayed["topology_hash"] == original["topology_hash"]
    assert replayed["order"] == original["order"]
    assert replayed["summary_id"] == original["summary_id"]
