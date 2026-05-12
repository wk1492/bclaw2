import json
from pathlib import Path

from ledger_writer import LedgerWriter, verify_ledger
from transcript_validator import validate_transcript_event, reconstruct_thread, TranscriptValidationError

TRANSCRIPT_EVENT_TYPE = "transcript.message"


def _existing_message_ids(path) -> set:
    return {r["message_id"] for r in load_ledger_lines(path) if "message_id" in r}


def append_transcript_event(event: dict, path) -> dict:
    validate_transcript_event(event)
    existing = _existing_message_ids(path)
    if event["message_id"] in existing:
        raise TranscriptValidationError(f"duplicate message_id: {event['message_id']}")
    pid = event.get("parent_message_id")
    if pid is not None and pid not in existing:
        raise TranscriptValidationError(f"parent_message_id not in ledger: {pid}")
    writer = LedgerWriter(path)
    return writer.append(dict(event))


def load_ledger_lines(path) -> list:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def replay_transcript_events(path) -> list:
    records = load_ledger_lines(path)
    transcript = [r for r in records if r.get("event_type") == TRANSCRIPT_EVENT_TYPE]
    return reconstruct_thread(transcript)


def replay_execution_events(path) -> list:
    records = load_ledger_lines(path)
    return [r for r in records if r.get("event_type") != TRANSCRIPT_EVENT_TYPE]


def verify_mixed_ledger(path) -> dict:
    return verify_ledger(path)
