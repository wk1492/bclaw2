from transcript_event import canonical_json, make_transcript_event
from transcript_ledger import (
    append_transcript_event,
    replay_execution_events,
    replay_transcript_events,
    verify_mixed_ledger,
)
from transcript_validator import validate_transcript_event
from model_runner import run_proposal

RUN_ID = "run_capture_001"
TS = "2026-05-13T12:00:00+00:00"
PROMPT = "Should the causal edge fatigue -> error_rate be included?"


class DeterministicFakeRunner:
    """Wraps run_proposal with fixed inputs. No network, no subprocess, no Ollama."""

    def __init__(self, run_id, sender, recipient, role, prompt):
        self._kwargs = dict(
            run_id=run_id, sender=sender, recipient=recipient,
            role=role, prompt=prompt,
        )

    def run(self) -> dict:
        return run_proposal(**self._kwargs)


def _make_runner():
    return DeterministicFakeRunner(RUN_ID, "agent_a", "agent_b", "proposal", PROMPT)


def _make_event(payload: dict) -> dict:
    return make_transcript_event(
        run_id=RUN_ID,
        sender="agent_a",
        recipient="agent_b",
        role="proposal",
        content=payload["content"],
        created_at=TS,
        metadata={"runner_output": payload},
    )


# 1. DeterministicFakeRunner.run() returns an output payload dict
def test_fake_runner_returns_payload():
    payload = _make_runner().run()
    assert isinstance(payload, dict)
    for key in ("run_id", "sender", "recipient", "role", "model_name",
                "prompt_hash", "content", "output_hash"):
        assert key in payload


# 2. Payload is embedded in transcript event metadata under "runner_output"
def test_payload_embedded_in_metadata():
    payload = _make_runner().run()
    event = _make_event(payload)
    assert "runner_output" in event["metadata"]
    assert event["metadata"]["runner_output"] == payload


# 3. Transcript event validates without schema changes
def test_event_validates():
    payload = _make_runner().run()
    event = _make_event(payload)
    validated = validate_transcript_event(event)
    assert validated is event


# 4. Append through transcript ledger succeeds
def test_append_succeeds(tmp_path):
    path = tmp_path / "ledger.jsonl"
    payload = _make_runner().run()
    event = _make_event(payload)
    result = append_transcript_event(event, path)
    assert result is not None
    assert path.exists()


# 5. Replay returns metadata byte-identical to what was appended
def test_replay_metadata_byte_identical(tmp_path):
    path = tmp_path / "ledger.jsonl"
    payload = _make_runner().run()
    event = _make_event(payload)
    append_transcript_event(event, path)

    replayed = replay_transcript_events(path)
    assert len(replayed) == 1
    assert replayed[0]["metadata"]["runner_output"] == payload
    assert canonical_json(replayed[0]["metadata"]) == canonical_json(event["metadata"])


# 6. Repeated runner → transcript → replay runs produce byte-identical message_id and metadata
def test_repeated_runs_byte_identical(tmp_path):
    path_a = tmp_path / "a.jsonl"
    path_b = tmp_path / "b.jsonl"

    for path in (path_a, path_b):
        payload = _make_runner().run()
        append_transcript_event(_make_event(payload), path)

    replay_a = replay_transcript_events(path_a)
    replay_b = replay_transcript_events(path_b)

    assert replay_a[0]["message_id"] == replay_b[0]["message_id"]
    assert canonical_json(replay_a[0]["metadata"]) == canonical_json(replay_b[0]["metadata"])


# 7. Execution replay ignores the transcript event
def test_execution_replay_ignores_transcript(tmp_path):
    path = tmp_path / "ledger.jsonl"
    payload = _make_runner().run()
    append_transcript_event(_make_event(payload), path)
    assert replay_execution_events(path) == []


# 8. verify_mixed_ledger passes after append
def test_verify_mixed_ledger_passes(tmp_path):
    path = tmp_path / "ledger.jsonl"
    payload = _make_runner().run()
    append_transcript_event(_make_event(payload), path)
    result = verify_mixed_ledger(path)
    assert result["ok"] is True
    assert result["failures"] == []
