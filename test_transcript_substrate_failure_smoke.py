import pytest

from transcript_event import make_transcript_event, canonical_json
from transcript_ledger import append_transcript_event, replay_transcript_events, verify_mixed_ledger
from transcript_validator import TranscriptValidationError


def test_invalid_append_has_zero_side_effects(tmp_path):
    ledger_path = tmp_path / "substrate_failure_smoke.jsonl"

    valid = make_transcript_event(
        run_id="run_smoke_001",
        sender="agent_a",
        recipient="broadcast",
        role="proposal",
        content="Add causal edge: stress -> performance_drop",
        created_at="2026-05-13T10:00:00+00:00",
    )
    append_transcript_event(valid, ledger_path)

    before_bytes = ledger_path.read_bytes()
    before_verify = verify_mixed_ledger(ledger_path)
    before_replay = canonical_json(replay_transcript_events(ledger_path))

    malformed = dict(valid)
    del malformed["sender"]

    with pytest.raises(TranscriptValidationError):
        append_transcript_event(malformed, ledger_path)

    after_bytes = ledger_path.read_bytes()
    after_verify = verify_mixed_ledger(ledger_path)
    after_replay = canonical_json(replay_transcript_events(ledger_path))

    assert before_bytes == after_bytes
    assert before_verify == after_verify
    assert before_replay == after_replay
    assert after_verify["ok"] is True
    assert len(replay_transcript_events(ledger_path)) == 1
