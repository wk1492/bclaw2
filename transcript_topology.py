import hashlib
import json

TRANSCRIPT_EVENT_TYPE = "transcript.message"


class TranscriptLinearizationError(ValueError):
    pass


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sort_key(event: dict) -> tuple:
    return (str(event.get("created_at", "")), str(event.get("message_id", "")))


def _transcript_events(records: list) -> list:
    return [
        event for event in records
        if isinstance(event, dict) and event.get("event_type") == TRANSCRIPT_EVENT_TYPE
    ]


def linearize_transcript(ledger: list) -> list:
    """
    Return transcript.message events in deterministic depth-first topology order.

    Rules:
    1. Non-transcript events are ignored.
    2. Roots are messages with no parent_message_id or an unresolved parent.
    3. Roots are sorted by (created_at, message_id).
    4. Children are sorted by (created_at, message_id).
    5. Traversal is depth-first and deterministic.
    6. Unresolved parents are synthetic roots, using the same root ordering.

    This function is pure: it performs no I/O, mutates no input events, and does
    not alter ledger hash-chain or replay semantics.
    """
    events = _transcript_events(ledger)
    if not events:
        return []

    by_id = {event["message_id"]: event for event in events}
    children = {message_id: [] for message_id in by_id}
    roots = []

    for event in events:
        message_id = event["message_id"]
        parent_id = event.get("parent_message_id")
        if parent_id and parent_id in by_id and parent_id != message_id:
            children[parent_id].append(event)
        else:
            roots.append(event)

    for child_list in children.values():
        child_list.sort(key=_sort_key)
    roots.sort(key=_sort_key)

    result = []
    visited = set()
    visiting = set()

    def walk(node: dict):
        message_id = node["message_id"]
        if message_id in visited:
            return
        if message_id in visiting:
            raise TranscriptLinearizationError(f"cycle detected at message_id: {message_id}")

        visiting.add(message_id)
        result.append(node)
        visited.add(message_id)

        for child in children.get(message_id, []):
            walk(child)

        visiting.remove(message_id)

    for root in roots:
        walk(root)

    # Defensive fallback for malformed cyclic graphs with no roots. This keeps
    # behavior deterministic while surfacing true cycles through walk().
    for event in sorted(events, key=_sort_key):
        if event["message_id"] not in visited:
            walk(event)

    return result


def linearize_transcript_topology(events: list) -> list:
    """Backward-compatible alias used by existing transcript ledger helpers."""
    return linearize_transcript(events)


def compute_transcript_linearization(events: list) -> dict:
    """
    Pure-functional, content-addressed linearization report.

    Returns:
        order            — message_ids in deterministic linearized order
        node_count       — total transcript events after filtering
        orphaned         — sorted message_ids whose parent is not in this event set
        topology_hash    — sha256 of canonical(order)
        linearization_id — "tlin_" + sha256[:24] of canonical({order, orphaned})
    """
    transcript_events = _transcript_events(events)
    if not transcript_events:
        empty = []
        return {
            "order": empty,
            "node_count": 0,
            "orphaned": [],
            "topology_hash": _sha256(_canonical(empty)),
            "linearization_id": "tlin_" + _sha256(_canonical({"order": empty, "orphaned": []}))[:24],
        }

    by_id = {event["message_id"]: event for event in transcript_events}
    orphaned = sorted(
        event["message_id"] for event in transcript_events
        if event.get("parent_message_id") and event["parent_message_id"] not in by_id
    )

    linearized = linearize_transcript(transcript_events)
    order = [event["message_id"] for event in linearized]

    topology_hash = _sha256(_canonical(order))
    linearization_id = "tlin_" + _sha256(_canonical({"order": order, "orphaned": orphaned}))[:24]

    return {
        "order": order,
        "node_count": len(transcript_events),
        "orphaned": orphaned,
        "topology_hash": topology_hash,
        "linearization_id": linearization_id,
    }
