"""
Derived epistemic graph view.

Pure function: list of replayed transcript events in, graph dict out.
No I/O. No caches. No hidden state. Input events never mutated.

Nodes:        epistemic claims keyed by stable claim ID.
Edges:        evidence relationships from evidence_refs.
Dangling refs: evidence_refs that resolve to no known epistemic node.

Claim IDs are stable across ledger append/replay round-trips because decoration
fields added by LedgerWriter (timestamp, event_hash, event_id, rolling_hash,
previous_hash) are excluded before computing the claim ID.
"""
from epistemic_event import EPISTEMIC_FIELDS, epistemic_claim_id

# Fields added by LedgerWriter.append — excluded before computing stable claim IDs.
_DECORATION_FIELDS = frozenset({
    "timestamp", "event_hash", "event_id", "rolling_hash", "previous_hash",
})


def _is_epistemic(event: dict) -> bool:
    return bool(EPISTEMIC_FIELDS & set(event.keys()))


def _stable_id(event: dict) -> str:
    """
    Compute a claim ID that is stable across ledger round-trips.
    For pre-ledger events this equals epistemic_claim_id(event) directly.
    For post-ledger (replayed) events decoration fields are stripped first.
    """
    return epistemic_claim_id(
        {k: v for k, v in event.items() if k not in _DECORATION_FIELDS}
    )


def derive_epistemic_graph(events: list) -> dict:
    """
    Derive a deterministic epistemic graph from replayed transcript events.

    Non-epistemic events (lacking all EPISTEMIC_FIELDS keys) are silently ignored.
    Input list and individual event dicts are never mutated.

    Returns a JSON-safe dict with keys:
        nodes         — {claim_id: node_info_dict} for each epistemic event
        edges         — sorted list of {source, target, relation} dicts
        node_count    — int
        edge_count    — int
        dangling_refs — sorted list of evidence_refs that resolve to no known node
    """
    epistemic = [e for e in events if _is_epistemic(e)]

    # Build nodes and message_id → claim_id index in one pass.
    nodes: dict = {}
    msg_to_cid: dict = {}
    for e in epistemic:
        cid = _stable_id(e)
        nodes[cid] = {
            "claim_id": cid,
            "message_id": e["message_id"],
            "claim_type": e.get("claim_type"),
            "epistemic_status": e.get("epistemic_status"),
            "confidence": e.get("confidence"),
            "sender": e.get("sender"),
            "role": e.get("role"),
        }
        msg_to_cid[e["message_id"]] = cid

    # Build edges from evidence_refs.
    edges: list = []
    dangling: set = set()
    for e in epistemic:
        source = _stable_id(e)
        for ref in e.get("evidence_refs", []):
            if ref in msg_to_cid:
                edges.append({
                    "source": source,
                    "target": msg_to_cid[ref],
                    "relation": "evidence",
                })
            else:
                dangling.add(ref)

    edges_sorted = sorted(edges, key=lambda x: (x["source"], x["target"]))

    return {
        "nodes": nodes,
        "edges": edges_sorted,
        "node_count": len(nodes),
        "edge_count": len(edges_sorted),
        "dangling_refs": sorted(dangling),
    }
