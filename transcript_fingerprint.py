"""
transcript_fingerprint.py — SUBSTRATE_VERSION=1

Deterministic topology fingerprint for transcript critique graphs.

Fingerprint depends only on:
  - normalized message_id
  - normalized parent_message_id
  - canonical topology ordering from transcript_topology

Invariants:
  - byte-stable across runs
  - ingestion-order independent
  - execution events ignored
  - unrelated metadata fields ignored
  - inputs never mutated
"""
from __future__ import annotations

import hashlib
import json

from transcript_topology import linearize_transcript_topology

_TRANSCRIPT = "transcript.message"


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_topology_fingerprint(events: list[dict]) -> str:
    """
    Return sha256 hex fingerprint of the canonical linearized topology.

    Steps:
      1. Filter to transcript.message events.
      2. Linearize deterministically via linearize_transcript_topology.
      3. Build (message_id, parent_message_id) tuples; missing parent → "".
      4. Canonical JSON → UTF-8 → sha256 hex.

    Same structure, any ingestion order → identical fingerprint.
    """
    linearized = linearize_transcript_topology(list(events))
    tuples = [
        [e["message_id"], e.get("parent_message_id") or None]
        for e in linearized
    ]
    payload = _canonical(tuples).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def fingerprint_report(events: list[dict]) -> dict:
    """JSON-safe report: fingerprint + node_count + root_count."""
    transcript = [e for e in events if e.get("event_type") == _TRANSCRIPT]
    roots = [e for e in transcript if not e.get("parent_message_id")]
    return {
        "fingerprint": compute_topology_fingerprint(events),
        "node_count": len(transcript),
        "root_count": len(roots),
    }
