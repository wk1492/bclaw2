import hashlib
import json


class TranscriptLinearizationError(ValueError):
    pass


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def linearize_transcript_topology(events: list) -> list:
    """
    Deterministic linearization of a transcript event graph.

    Ordering rules:
    1. Root nodes (no parent) first.
    2. Children after parent (parent_message_id dependency).
    3. Arbiter/synthesis nodes after all referenced events (references dependency).
    4. Siblings sorted by (created_at, message_id) as deterministic tie-break.
    5. Disconnected nodes handled by same tie-break.
    """
    if not events:
        return []

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

        ready.sort(key=lambda mid: (by_id[mid].get("created_at", ""), mid))
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
    if not events:
        empty: list = []
        return {
            "order": empty,
            "node_count": 0,
            "orphaned": [],
            "topology_hash": _sha256(_canonical(empty)),
            "linearization_id": "tlin_" + _sha256(_canonical({"order": empty, "orphaned": []}))[:24],
        }

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
        emitted.add(min(ready, key=lambda mid: (by_id[mid].get("created_at", ""), mid)))
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
