import json
import pytest
from pathlib import Path

from transcript_agent_loop import run_transcript_agent_loop
from transcript_ledger import replay_execution_events, verify_mixed_ledger
from ledger_writer import LedgerWriter


def test_agent_loop_emits_exactly_three_events(tmp_path):
    path = tmp_path / "ledger.jsonl"
    summary = run_transcript_agent_loop(path)
    assert summary["event_count"] == 3


def test_agent_loop_roles_are_proposal_critique_arbiter(tmp_path):
    path = tmp_path / "ledger.jsonl"
    summary = run_transcript_agent_loop(path)
    assert summary["roles"] == ["proposal", "critique", "arbiter"]


def test_agent_loop_replayed_order_is_deterministic(tmp_path):
    path = tmp_path / "ledger.jsonl"
    s1 = run_transcript_agent_loop(path)
    path2 = tmp_path / "ledger2.jsonl"
    s2 = run_transcript_agent_loop(path2)
    assert s1["replay_order"] == s2["replay_order"]


def test_agent_loop_parent_reference_relationships(tmp_path):
    path = tmp_path / "ledger.jsonl"
    summary = run_transcript_agent_loop(path)
    ids = summary["replay_order"]
    rels = summary["parent_relationships"]
    assert rels[ids[0]] is None
    assert rels[ids[1]] == ids[0]
    assert rels[ids[2]] == ids[1]


def test_agent_loop_execution_replay_ignores_transcript_events(tmp_path):
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    writer.append({"type": "execution.event", "payload": {"x": 1}})
    run_transcript_agent_loop(path)
    writer2 = LedgerWriter(path)
    writer2.append({"type": "execution.event", "payload": {"x": 2}})

    exec_events = replay_execution_events(path)
    assert len(exec_events) == 2
    assert exec_events[0]["payload"] == {"x": 1}
    assert exec_events[1]["payload"] == {"x": 2}


def test_agent_loop_repeated_runs_byte_identical_summary(tmp_path):
    path1 = tmp_path / "ledger1.jsonl"
    path2 = tmp_path / "ledger2.jsonl"
    s1 = run_transcript_agent_loop(path1)
    s2 = run_transcript_agent_loop(path2)
    assert json.dumps(s1, sort_keys=True, separators=(",", ":")) == \
           json.dumps(s2, sort_keys=True, separators=(",", ":"))


def test_agent_loop_hash_chain_passes(tmp_path):
    path = tmp_path / "ledger.jsonl"
    summary = run_transcript_agent_loop(path)
    assert summary["hash_chain_ok"] is True
    result = verify_mixed_ledger(path)
    assert result["failures"] == []
    assert result["count"] == 3
