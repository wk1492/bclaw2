import json
import os
import tempfile

import pytest

from transcript_event import make_transcript_event
from transcript_ledger import append_transcript_event, replay_transcript_events, verify_mixed_ledger
from transcript_validator import TranscriptValidationError

RUN_ID = "run_failure_smoke"
TS_A = "2026-05-13T10:00:00+00:00"


def _fresh():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.unlink(path)
    return path


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def test_invalid_append_has_zero_side_effects():
    path = _fresh()

    valid = make_transcript_event(
        run_id=RUN_ID, sender="agent_a", recipient="broadcast",
        role="proposal", content="Add causal edge: stress -> performance_drop",
        created_at=TS_A,
    )
    append_transcript_event(valid, path)

    before_bytes = open(path, "rb").read()
    before_verify = _canon(verify_mixed_ledger(path))
    before_replay = _canon(replay_transcript_events(path))

    malformed = dict(valid)
    del malformed["sender"]

    with pytest.raises(TranscriptValidationError, match="missing required fields"):
        append_transcript_event(malformed, path)

    after_bytes = open(path, "rb").read()
    after_verify = _canon(verify_mixed_ledger(path))
    after_replay = _canon(replay_transcript_events(path))

    assert before_bytes == after_bytes
    assert before_verify == after_verify
    assert before_replay == after_replay
    assert json.loads(after_verify)["ok"] is True
    assert len(replay_transcript_events(path)) == 1
