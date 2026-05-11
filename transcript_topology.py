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
