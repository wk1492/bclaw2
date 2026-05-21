import hashlib
import json

TRANSCRIPT_EVENT_TYPE = "transcript.message"


class TranscriptLinearizationError(ValueError):
    pass


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _transcript_only(events: list) -> list:
    """Return only transcript.message events; silently drop all others."""
    return [e for e in events if e.get("event_type") == TRANSCRIPT_EVENT_TYPE]


def linearize_transcript_topology(events: list) -> list:
    """
    Deterministic linearization of a transcript event graph.

    Ordering rules:
    1. Root nodes (no parent) first.
    2. Children after parent (parent_message_id dependency).
    3. Arbiter/synthesis nodes after all referenced events (references dependency).
    4. Siblings sorted by canonical normalized UTF-8 message_id bytes.
    5. Final tie-break by original input index. No timestamp dependence.

    Non-transcript events (event_type != 'transcript.message') are silently ignored.
    """
    events = _transcript_only(events)
    if not events:
        return []

    input_index = {e["message_id"]: i for i, e in enumerate(events)}
    by_id = {e["message_id"]: e for e in events}

    deps: dict[str, set] = {}
    for e in events:
        node_deps: set[str] = set()
        parent = e.get("parent_message_id")
        if parent and parent in by_id:
            node_deps.add(parent)
        for ref in e.get("references", []):
            if ref in by_id:
                node_deps.add(ref)
        deps[e["message_id"]] = node_deps

    remaining = {e["message_id"] for e in events}
    emitted: set[str] = set()
    result = []

    while remaining:
        ready = [mid for mid in remaining if deps[mid].issubset(emitted)]
        if not ready:
            ready = list(remaining)

        ready.sort(key=lambda mid: (mid.encode("utf-8"), input_index[mid]))
        chosen = ready[0]

        result.append(by_id[chosen])
        emitted.add(chosen)
        remaining.discard(chosen)

    return result


def compute_transcript_linearization(events: list) -> dict:
    """
    Pure-functional, content-addressed linearization report.

    Does not perform ledger I/O. Raises TranscriptLinearizationError on cycles.

    Returns:
        order            — message_ids in deterministic linearized order
        node_count       — total transcript events
        orphaned         — sorted message_ids whose parent is not in this event set
        topology_hash    — sha256 of canonical(order)
        linearization_id — "tlin_" + sha256[:24] of canonical({order, orphaned})
    """
    events = _transcript_only(events)
    if not events:
        empty: list = []
        return {
            "order": empty,
            "node_count": 0,
            "orphaned": [],
            "topology_hash": _sha256(_canonical(empty)),
            "linearization_id": "tlin_" + _sha256(_canonical({"order": empty, "orphaned": []}))[:24],
        }

    input_index = {e["message_id"]: i for i, e in enumerate(events)}
    by_id = {e["message_id"]: e for e in events}

    orphaned = sorted(
        e["message_id"] for e in events
        if e.get("parent_message_id") and e["parent_message_id"] not in by_id
    )

    # Cycle detection via Kahn's: if no ready node exists while nodes remain, cycle found.
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
            raise TranscriptLinearizationError(
                f"Cycle detected in transcript topology involving "
                f"{len(remaining)} node(s): {sorted(remaining)}"
            )
        emitted.add(min(ready, key=lambda mid: (mid.encode("utf-8"), input_index[mid])))
        remaining -= emitted

    linearized = linearize_transcript_topology(events)
    order = [e["message_id"] for e in linearized]

    topology_hash = _sha256(_canonical(order))
    linearization_id = "tlin_" + _sha256(_canonical({"order": order, "orphaned": orphaned}))[:24]

    return {
        "order": order,
        "node_count": len(events),
        "orphaned": orphaned,
        "topology_hash": topology_hash,
        "linearization_id": linearization_id,
    }
