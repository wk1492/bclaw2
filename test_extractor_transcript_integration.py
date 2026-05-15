"""
Phase 2A integration: extractor operating on a full ledger-backed transcript.

Proves the pipeline: run_two_agent_handoff → replay_transcript_events
→ extract_from_transcript produces a valid, deterministic artifact.

No ledger writes after extraction. No model calls. No FCM mutation.
"""
import os
import tempfile

from epistemic_extractor import EXTRACTOR_VERSION, extract_from_transcript
from transcript_ledger import replay_transcript_events
from transcript_llm_agent import run_two_agent_handoff


def _fresh_path():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.unlink(path)
    return path


def _run():
    path = _fresh_path()
    result = run_two_agent_handoff(path)
    events = replay_transcript_events(path)
    artifact = extract_from_transcript(events)
    return result, events, artifact


# 1. Artifact has all required top-level keys
def test_artifact_has_required_keys():
    _, _, artifact = _run()
    for key in ("artifact_id", "version", "results", "block_count", "error_count"):
        assert key in artifact, f"missing key: {key}"


# 2. One result entry per replayed event
def test_result_count_matches_event_count():
    _, events, artifact = _run()
    assert len(artifact["results"]) == len(events)


# 3. Result message_ids match replayed event message_ids in order
def test_result_message_ids_match_events():
    _, events, artifact = _run()
    event_ids = [e["message_id"] for e in events]
    result_ids = [r["message_id"] for r in artifact["results"]]
    assert result_ids == event_ids


# 4. Prose-only transcript yields block_count=0, error_count=0
def test_prose_transcript_zero_blocks():
    _, _, artifact = _run()
    assert artifact["block_count"] == 0
    assert artifact["error_count"] == 0


# 5. All result entries report ok=True for prose-only events
def test_prose_events_all_ok():
    _, _, artifact = _run()
    assert all(r["ok"] for r in artifact["results"])


# 6. artifact_id is a 64-char hex sha256
def test_artifact_id_is_hex64():
    _, _, artifact = _run()
    aid = artifact["artifact_id"]
    assert len(aid) == 64
    assert all(c in "0123456789abcdef" for c in aid)


# 7. artifact version matches EXTRACTOR_VERSION
def test_artifact_version():
    _, _, artifact = _run()
    assert artifact["version"] == EXTRACTOR_VERSION


# 8. Repeated extraction from identical ledger produces same artifact_id
def test_extraction_is_deterministic():
    path = _fresh_path()
    run_two_agent_handoff(path)
    events = replay_transcript_events(path)
    id1 = extract_from_transcript(events)["artifact_id"]
    id2 = extract_from_transcript(events)["artifact_id"]
    assert id1 == id2


# 9. Chain_ok from handoff is unaffected by extraction
def test_handoff_chain_unaffected():
    path = _fresh_path()
    result = run_two_agent_handoff(path)
    events = replay_transcript_events(path)
    extract_from_transcript(events)  # extraction must not mutate ledger
    from transcript_ledger import verify_mixed_ledger
    chain = verify_mixed_ledger(path)
    assert chain.get("ok") is True
    assert result["chain_ok"] is True
