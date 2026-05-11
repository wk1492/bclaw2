import json
from pathlib import Path

from ledger_writer import LedgerWriter, verify_ledger
from transcript_validator import validate_transcript_event, reconstruct_thread

TRANSCRIPT_EVENT_TYPE = "transcript.message"


def append_transcript_event(event: dict, path) -> dict:
    validate_transcript_event(event)
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
