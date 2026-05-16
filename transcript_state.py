import json

from transcript_topology import linearize_transcript_topology

TRANSCRIPT_EVENT_TYPE = "transcript.message"


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def reduce_transcript_state(events: list) -> dict:
    """
    Pure, order-independent reducer over transcript.message events.
    Non-transcript events are silently ignored.
    Deduplicates by message_id (first occurrence wins).
    Produces a JSON-safe canonical state dict with stable ordering throughout.
    """
    transcript = [e for e in events if e.get("event_type") == TRANSCRIPT_EVENT_TYPE]

    seen: set = set()
    unique: list = []
    for e in transcript:
        mid = e.get("message_id")
        if mid and mid not in seen:
            seen.add(mid)
            unique.append(e)
    events = unique

    if not events:
        return {
            "message_count":        0,
            "proposal_count":       0,
            "critique_count":       0,
            "arbiter_count":        0,
            "participants":         [],
            "root_message_ids":     [],
            "unresolved_message_ids": [],
            "latest_role":          None,
            "latest_message_id":    None,
            "topology_edges":       [],
            "topology_order":       [],
        }

    by_id = {e["message_id"]: e for e in events}

    proposals = [e for e in events if e.get("role") == "proposal"]
    critiques  = [e for e in events if e.get("role") == "critique"]
    arbiters   = [e for e in events if e.get("role") == "arbiter"]

    participants = sorted({e.get("sender", "") for e in events if e.get("sender")})

    root_message_ids = sorted(
        e["message_id"] for e in events
        if not e.get("parent_message_id") or e["parent_message_id"] not in by_id
    )

    arbiter_refs: set = set()
    for arb in arbiters:
        arbiter_refs.update(arb.get("references", []))
    unresolved_message_ids = sorted(
        c["message_id"] for c in critiques if c["message_id"] not in arbiter_refs
    )

    linearized = linearize_transcript_topology(events)
    latest = linearized[-1]
    topology_order = [e["message_id"] for e in linearized]

    edge_set: set = set()
    for e in events:
        mid = e["message_id"]
        parent = e.get("parent_message_id")
        if parent and parent in by_id:
            edge_set.add((parent, mid))
        for ref in e.get("references", []):
            if ref in by_id:
                edge_set.add((ref, mid))
    topology_edges = sorted([list(pair) for pair in edge_set])

    return {
        "message_count":          len(events),
        "proposal_count":         len(proposals),
        "critique_count":         len(critiques),
        "arbiter_count":          len(arbiters),
        "participants":           participants,
        "root_message_ids":       root_message_ids,
        "unresolved_message_ids": unresolved_message_ids,
        "latest_role":            latest["role"],
        "latest_message_id":      latest["message_id"],
        "topology_edges":         topology_edges,
        "topology_order":         topology_order,
    }
