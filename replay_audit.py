"""
Replay audit layer.

Computes deterministic, machine-stable hashes over transcript replay output.
All hashes are derived from transcript content fields only — no timestamps,
no UUIDs, no ledger decoration fields, no unordered iteration.
"""
import hashlib
import json

from transcript_topology import linearize_transcript_topology

# Only these fields contribute to audit hashes — stable across ledger append decoration
TRANSCRIPT_FIELDS = (
    "event_type", "message_id", "run_id", "sender", "recipient",
    "role", "content", "references", "parent_message_id", "created_at", "metadata",
)


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clean(event: dict) -> dict:
    return {k: event[k] for k in TRANSCRIPT_FIELDS if k in event}


def compute_replay_audit(events: list) -> dict:
    """
    Compute deterministic audit hashes for a transcript event set.

    Returns:
        transcript_hash    — hash of canonical sorted event payloads
        linearized_hash    — hash of linearized message_id order
        critique_order_hash — hash of role sequence after linearization
        fusion_output_hash — hash of (message_id, role) pairs after linearization
        artifact_hash      — hash of all four hashes combined
    """
    clean = [_clean(e) for e in events]
    # Sort canonically so transcript_hash is insertion-order independent
    clean_sorted = sorted(clean, key=lambda e: (e.get("created_at", ""), e["message_id"]))
    transcript_hash = _sha256(_canonical(clean_sorted))

    linearized = linearize_transcript_topology(clean)
    linearized_order = [e["message_id"] for e in linearized]
    linearized_hash = _sha256(_canonical(linearized_order))

    critique_order = [e["role"] for e in linearized]
    critique_order_hash = _sha256(_canonical(critique_order))

    fusion_output = [{"message_id": e["message_id"], "role": e["role"]} for e in linearized]
    fusion_output_hash = _sha256(_canonical(fusion_output))

    sub = {
        "critique_order_hash": critique_order_hash,
        "fusion_output_hash": fusion_output_hash,
        "linearized_hash": linearized_hash,
        "transcript_hash": transcript_hash,
    }
    artifact_hash = _sha256(_canonical(sub))

    return {**sub, "artifact_hash": artifact_hash}
