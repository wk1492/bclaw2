"""
Frozen extractor baseline verification.
Re-runs the deterministic two-agent handoff and asserts the extraction
artifact matches the frozen artifact at HEAD 1052724.
"""
import json
import os
import tempfile
from pathlib import Path

from epistemic_extractor import extract_from_transcript
from transcript_ledger import replay_transcript_events
from transcript_llm_agent import run_two_agent_handoff

ARTIFACT_PATH = (
    Path(__file__).parent / "artifacts/baselines/extractor_baseline_1052724.json"
)
FROZEN = json.loads(ARTIFACT_PATH.read_text())


def _run_extraction():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.unlink(path)
    run_two_agent_handoff(path)
    events = replay_transcript_events(path)
    return extract_from_transcript(events)


def test_frozen_artifact_id():
    artifact = _run_extraction()
    assert artifact["artifact_id"] == FROZEN["artifact_id"], (
        f"artifact_id changed: {artifact['artifact_id']!r} != {FROZEN['artifact_id']!r}"
    )


def test_frozen_block_count():
    artifact = _run_extraction()
    assert artifact["block_count"] == FROZEN["block_count"]


def test_frozen_version():
    artifact = _run_extraction()
    assert artifact["version"] == FROZEN["version"]


def test_frozen_message_ids():
    artifact = _run_extraction()
    live_ids = [r["message_id"] for r in artifact["results"]]
    frozen_ids = [r["message_id"] for r in FROZEN["results"]]
    assert live_ids == frozen_ids, f"message_ids changed: {live_ids} != {frozen_ids}"
