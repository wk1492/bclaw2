from __future__ import annotations
import json
import pytest
from authority_coherence_report import (
    compute_coherence_hash,
    make_coherence_report,
    validate_coherence_report,
)

_BASE = dict(
    query_surface="surface.test",
    ontology_version="v1.0",
    branch="main",
    resolution_hashes=["abc123", "def456"],
    status="coherent",
    conflicts=[],
    ambiguous_authorities=[],
    orphaned_surfaces=[],
    checked_at="2026-01-01T00:00:00Z",
)

def _make(**overrides):
    return make_coherence_report(**{**_BASE, **overrides})

def test_valid_coherent_report():
    r = _make()
    assert r["status"] == "coherent"
    assert "coherence_hash" in r
    validate_coherence_report(r)

def test_valid_incoherent_report():
    r = _make(status="incoherent", conflicts=[{"a": "x", "b": "y"}])
    assert r["status"] == "incoherent"
    validate_coherence_report(r)

def test_missing_required_field_fails():
    r = _make()
    del r["query_surface"]
    with pytest.raises(ValueError, match="missing required fields"):
        validate_coherence_report(r)

def test_invalid_status_fails():
    with pytest.raises(ValueError, match="Invalid status"):
        _make(status="unknown_status")

def test_checked_at_excluded_from_hash():
    r1 = _make(checked_at="2026-01-01T00:00:00Z")
    r2 = _make(checked_at="2026-05-22T12:00:00Z")
    assert r1["coherence_hash"] == r2["coherence_hash"]
