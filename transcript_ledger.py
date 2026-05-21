import hashlib
import json
from pathlib import Path

from ledger_writer import LedgerWriter, verify_ledger
from transcript_topology import linearize_transcript_topology
from transcript_validator import validate_transcript_event, reconstruct_thread, TranscriptValidationError

TRANSCRIPT_EVENT_TYPE = "transcript.message"


class TranscriptTopologyError(ValueError):
    pass


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def replay_transcript_topology(path) -> dict:
    """
    Read transcript.message events from ledger and return canonical topology metadata.

    Does not alter ledger state, hash-chain, or replay_transcript_events behavior.
    Raises TranscriptTopologyError if a dependency cycle is detected.

    Returns JSON-safe dict:
      order         — message_ids in deterministic linearized order
      node_count    — total transcript events found
      orphaned      — message_ids whose parent_message_id is not in this event set
      topology_hash — sha256 of canonical(order)
    """
    records = load_ledger_lines(path)
    events = [r for r in records if r.get("event_type") == TRANSCRIPT_EVENT_TYPE]

    if not events:
        empty_order: list = []
        return {
            "order": empty_order,
            "node_count": 0,
            "orphaned": [],
            "topology_hash": _sha256(_canonical(empty_order)),
        }

    input_index = {e["message_id"]: i for i, e in enumerate(events)}
    by_id = {e["message_id"]: e for e in events}

    orphaned = sorted(
        e["message_id"] for e in events
        if e.get("parent_message_id") and e["parent_message_id"] not in by_id
    )

    # Cycle detection: Kahn's algorithm — if ready set empties while nodes remain,
    # all remaining nodes are part of a cycle.
    deps: dict = {}
    for e in events:
        node_deps: set = set()
        parent = e.get("parent_message_id")
        if parent and parent in by_id:
            node_deps.add(parent)
        for ref in e.get("references", []):
            if ref in by_id:
                node_deps.add(ref)
        deps[e["message_id"]] = node_deps

    remaining = set(by_id.keys())
    emitted: set = set()
    while remaining:
        ready = [mid for mid in remaining if deps[mid].issubset(emitted)]
        if not ready:
            raise TranscriptTopologyError(
                f"Cycle detected in transcript topology involving "
                f"{len(remaining)} node(s): {sorted(remaining)}"
            )
        emitted.add(min(ready, key=lambda mid: (mid.encode("utf-8"), input_index[mid])))
        remaining -= emitted

    linearized = linearize_transcript_topology(events)
    order = [e["message_id"] for e in linearized]

    return {
        "order": order,
        "node_count": len(events),
        "orphaned": orphaned,
        "topology_hash": _sha256(_canonical(order)),
    }
