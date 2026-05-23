"""
authority_coherence_report.py — SUBSTRATE_VERSION=1

Data contract for surface-scoped authority coherence reports.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

VALID_STATUSES = frozenset({"coherent", "incoherent", "ambiguous", "orphaned"})

REQUIRED_FIELDS = frozenset({
    "query_surface",
    "ontology_version",
    "branch",
    "resolution_hashes",
    "status",
    "conflicts",
    "ambiguous_authorities",
    "orphaned_surfaces",
    "checked_at",
    "coherence_hash",
})

def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def compute_coherence_hash(
    query_surface: str,
    ontology_version: str,
    branch: str,
    resolution_hashes: list[str],
    status: str,
    conflicts: list[dict],
    ambiguous_authorities: list[dict],
    orphaned_surfaces: list[str],
) -> str:
    payload = {
        "query_surface": query_surface,
        "ontology_version": ontology_version,
        "branch": branch,
        "resolution_hashes": resolution_hashes,
        "status": status,
        "conflicts": conflicts,
        "ambiguous_authorities": ambiguous_authorities,
        "orphaned_surfaces": orphaned_surfaces,
    }
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()

def make_coherence_report(
    query_surface: str,
    ontology_version: str,
    branch: str,
    resolution_hashes: list[str],
    status: str,
    conflicts: list[dict],
    ambiguous_authorities: list[dict],
    orphaned_surfaces: list[str],
    checked_at: str,
) -> dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status {status!r}. Must be one of {sorted(VALID_STATUSES)}")

    coherence_hash = compute_coherence_hash(
        query_surface=query_surface,
        ontology_version=ontology_version,
        branch=branch,
        resolution_hashes=list(resolution_hashes),
        status=status,
        conflicts=list(conflicts),
        ambiguous_authorities=list(ambiguous_authorities),
        orphaned_surfaces=list(orphaned_surfaces),
    )

    return {
        "query_surface": query_surface,
        "ontology_version": ontology_version,
        "branch": branch,
        "resolution_hashes": list(resolution_hashes),
        "status": status,
        "conflicts": list(conflicts),
        "ambiguous_authorities": list(ambiguous_authorities),
        "orphaned_surfaces": list(orphaned_surfaces),
        "checked_at": checked_at,
        "coherence_hash": coherence_hash,
    }

def validate_coherence_report(report: dict[str, Any]) -> None:
    missing = REQUIRED_FIELDS - set(report.keys())
    if missing:
        raise ValueError(f"CoherenceReport missing required fields: {sorted(missing)}")
    if report["status"] not in VALID_STATUSES:
        raise ValueError(f"Invalid status {report['status']!r}")
