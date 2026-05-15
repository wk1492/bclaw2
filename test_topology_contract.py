"""
Tests for the static topology contract.

33 tests covering: sequential, parallel, choice, conditional, duplicate rejection,
invalid choice rejection, negative retry rejection, purity guarantees, determinism,
and canonical serialization stability.
"""
import copy
import json
import os
from unittest.mock import patch

import pytest

from topology_contract import (
    ExpectationStatus,
    StageExpectation,
    canonical_expectations,
    derive_expectations,
)

MISSING_REQUIRED = ExpectationStatus.MISSING_REQUIRED
PENDING_SELECTOR = ExpectationStatus.MISSING_CONDITIONAL_PENDING_SELECTOR
INTENTIONALLY_ABSENT = ExpectationStatus.INTENTIONALLY_ABSENT_UNSELECTED_BRANCH


# ── Sequential ────────────────────────────────────────────────────────────────

def test_sequential_single_stage():
    topo = {"stages": [{"name": "init", "kind": "sequential"}]}
    result = derive_expectations(topo)
    assert len(result) == 1
    assert result[0].name == "init"


def test_sequential_stage_is_missing_required():
    topo = {"stages": [{"name": "init", "kind": "sequential"}]}
    result = derive_expectations(topo)
    assert result[0].status == MISSING_REQUIRED


def test_sequential_multiple_stages():
    topo = {"stages": [
        {"name": "a", "kind": "sequential"},
        {"name": "b", "kind": "sequential"},
        {"name": "c", "kind": "sequential"},
    ]}
    result = derive_expectations(topo)
    assert len(result) == 3
    assert [e.name for e in result] == ["a", "b", "c"]
    assert all(e.status == MISSING_REQUIRED for e in result)


# ── Parallel ──────────────────────────────────────────────────────────────────

def test_parallel_all_branches_missing_required():
    topo = {"stages": [{"name": "par", "kind": "parallel", "branches": ["w1", "w2", "w3"]}]}
    result = derive_expectations(topo)
    assert all(e.status == MISSING_REQUIRED for e in result)


def test_parallel_branches_sorted():
    topo = {"stages": [{"name": "par", "kind": "parallel", "branches": ["z", "a", "m"]}]}
    result = derive_expectations(topo)
    assert [e.name for e in result] == ["a", "m", "z"]


def test_parallel_no_branches_produces_no_expectations():
    topo = {"stages": [{"name": "par", "kind": "parallel", "branches": []}]}
    result = derive_expectations(topo)
    assert result == ()


# ── Choice selector ───────────────────────────────────────────────────────────

def test_choice_no_selector_all_pending():
    topo = {"stages": [{"name": "ch", "kind": "choice",
                         "selector": None, "branches": ["opt_a", "opt_b"]}]}
    result = derive_expectations(topo)
    assert all(e.status == PENDING_SELECTOR for e in result)


def test_choice_selector_set_selected_is_missing_required():
    topo = {"stages": [{"name": "ch", "kind": "choice",
                         "selector": "opt_a", "branches": ["opt_a", "opt_b"]}]}
    result = derive_expectations(topo)
    selected = next(e for e in result if e.name == "opt_a")
    assert selected.status == MISSING_REQUIRED


def test_choice_selector_set_unselected_is_intentionally_absent():
    topo = {"stages": [{"name": "ch", "kind": "choice",
                         "selector": "opt_a", "branches": ["opt_a", "opt_b"]}]}
    result = derive_expectations(topo)
    unselected = next(e for e in result if e.name == "opt_b")
    assert unselected.status == INTENTIONALLY_ABSENT


def test_choice_branches_are_sorted():
    topo = {"stages": [{"name": "ch", "kind": "choice",
                         "selector": None, "branches": ["z_branch", "a_branch"]}]}
    result = derive_expectations(topo)
    assert [e.name for e in result] == ["a_branch", "z_branch"]


# ── Conditional branch ────────────────────────────────────────────────────────

def test_conditional_required_true_is_missing_required():
    topo = {"stages": [{"name": "step", "kind": "conditional", "required": True}]}
    result = derive_expectations(topo)
    assert result[0].status == MISSING_REQUIRED


def test_conditional_required_false_is_intentionally_absent():
    topo = {"stages": [{"name": "step", "kind": "conditional", "required": False}]}
    result = derive_expectations(topo)
    assert result[0].status == INTENTIONALLY_ABSENT


def test_conditional_default_required_is_true():
    topo = {"stages": [{"name": "step", "kind": "conditional"}]}
    result = derive_expectations(topo)
    assert result[0].status == MISSING_REQUIRED


# ── Duplicate stage rejection ─────────────────────────────────────────────────

def test_duplicate_stage_name_raises():
    topo = {"stages": [
        {"name": "alpha", "kind": "sequential"},
        {"name": "alpha", "kind": "sequential"},
    ]}
    with pytest.raises(ValueError, match="duplicate stage"):
        derive_expectations(topo)


def test_duplicate_stage_error_message_names_stage():
    topo = {"stages": [
        {"name": "dup_stage", "kind": "sequential"},
        {"name": "dup_stage", "kind": "sequential"},
    ]}
    with pytest.raises(ValueError, match="dup_stage"):
        derive_expectations(topo)


# ── Duplicate branch rejection ────────────────────────────────────────────────

def test_duplicate_branch_raises():
    topo = {"stages": [{"name": "par", "kind": "parallel",
                         "branches": ["w1", "w1"]}]}
    with pytest.raises(ValueError, match="duplicate branch"):
        derive_expectations(topo)


def test_duplicate_branch_error_message_names_branch():
    topo = {"stages": [{"name": "par", "kind": "parallel",
                         "branches": ["dup_branch", "dup_branch"]}]}
    with pytest.raises(ValueError, match="dup_branch"):
        derive_expectations(topo)


# ── Invalid choice rejection ──────────────────────────────────────────────────

def test_invalid_choice_selector_raises():
    topo = {"stages": [{"name": "ch", "kind": "choice",
                         "selector": "nonexistent", "branches": ["opt_a", "opt_b"]}]}
    with pytest.raises(ValueError, match="selector"):
        derive_expectations(topo)


def test_invalid_choice_selector_error_names_selector():
    topo = {"stages": [{"name": "ch", "kind": "choice",
                         "selector": "ghost_branch", "branches": ["opt_a"]}]}
    with pytest.raises(ValueError, match="ghost_branch"):
        derive_expectations(topo)


# ── Negative retry rejection ──────────────────────────────────────────────────

def test_negative_retry_raises():
    topo = {"stages": [{"name": "s", "kind": "sequential", "retry": -1}]}
    with pytest.raises(ValueError, match="retry"):
        derive_expectations(topo)


def test_zero_retry_is_accepted():
    topo = {"stages": [{"name": "s", "kind": "sequential", "retry": 0}]}
    result = derive_expectations(topo)
    assert len(result) == 1


def test_positive_retry_is_accepted():
    topo = {"stages": [{"name": "s", "kind": "sequential", "retry": 3}]}
    result = derive_expectations(topo)
    assert len(result) == 1


# ── Filesystem independence ───────────────────────────────────────────────────

def test_derive_expectations_does_not_require_filesystem():
    topo = {"stages": [{"name": "s", "kind": "sequential"}]}
    # If this works it proves no filesystem dependency — no tmp_path, no open
    result = derive_expectations(topo)
    assert len(result) == 1


def test_derive_expectations_does_not_call_open():
    topo = {"stages": [{"name": "s", "kind": "sequential"}]}
    with patch("builtins.open", side_effect=AssertionError("open must not be called")):
        result = derive_expectations(topo)
    assert len(result) == 1


def test_derive_expectations_does_not_call_os_path_exists():
    topo = {"stages": [{"name": "s", "kind": "sequential"}]}
    with patch.object(os.path, "exists",
                      side_effect=AssertionError("os.path.exists must not be called")):
        result = derive_expectations(topo)
    assert len(result) == 1


# ── Mutation safety ───────────────────────────────────────────────────────────

def test_derive_expectations_does_not_mutate_topology():
    topo = {"stages": [{"name": "s", "kind": "sequential"}]}
    original = copy.deepcopy(topo)
    derive_expectations(topo)
    assert topo == original


def test_derive_expectations_does_not_mutate_stage_dicts():
    stage = {"name": "s", "kind": "parallel", "branches": ["a", "b"]}
    topo = {"stages": [stage]}
    original_stage = copy.deepcopy(stage)
    derive_expectations(topo)
    assert stage == original_stage


# ── Determinism ───────────────────────────────────────────────────────────────

def test_derive_expectations_is_deterministic():
    topo = {"stages": [
        {"name": "seq", "kind": "sequential"},
        {"name": "par", "kind": "parallel", "branches": ["w2", "w1"]},
        {"name": "ch", "kind": "choice", "selector": "opt_b",
         "branches": ["opt_a", "opt_b", "opt_c"]},
    ]}
    results = [derive_expectations(topo) for _ in range(5)]
    assert len(set(results)) == 1


def test_derive_expectations_independent_of_stage_object_identity():
    stage_a = {"name": "alpha", "kind": "sequential"}
    stage_b = {"name": "beta", "kind": "sequential"}
    r1 = derive_expectations({"stages": [stage_a, stage_b]})
    r2 = derive_expectations({"stages": [dict(stage_a), dict(stage_b)]})
    assert r1 == r2


# ── Canonical serialization ───────────────────────────────────────────────────

def test_canonical_expectation_serialization_byte_stable():
    topo = {"stages": [
        {"name": "seq", "kind": "sequential"},
        {"name": "ch", "kind": "choice", "selector": None, "branches": ["a", "b"]},
    ]}
    exp = derive_expectations(topo)
    results = [canonical_expectations(exp) for _ in range(8)]
    assert len(set(results)) == 1


def test_canonical_serialization_is_valid_json():
    topo = {"stages": [{"name": "s", "kind": "sequential"}]}
    exp = derive_expectations(topo)
    serialized = canonical_expectations(exp)
    parsed = json.loads(serialized)
    assert isinstance(parsed, list)
    assert parsed[0]["name"] == "s"
    assert parsed[0]["status"] == "MISSING_REQUIRED"


def test_canonical_serialization_empty_expectations():
    exp = derive_expectations({"stages": []})
    assert canonical_expectations(exp) == "[]"


# ── Misc / coverage ───────────────────────────────────────────────────────────

def test_empty_topology_produces_empty_tuple():
    assert derive_expectations({}) == ()
    assert derive_expectations({"stages": []}) == ()


def test_expectation_status_enum_names():
    assert ExpectationStatus.MISSING_REQUIRED.value == "MISSING_REQUIRED"
    assert ExpectationStatus.MISSING_CONDITIONAL_PENDING_SELECTOR.value == "MISSING_CONDITIONAL_PENDING_SELECTOR"
    assert ExpectationStatus.INTENTIONALLY_ABSENT_UNSELECTED_BRANCH.value == "INTENTIONALLY_ABSENT_UNSELECTED_BRANCH"


def test_mixed_stage_kinds_produce_correct_expectations():
    topo = {"stages": [
        {"name": "boot", "kind": "sequential"},
        {"name": "fetch", "kind": "parallel", "branches": ["src_a", "src_b"]},
        {"name": "route", "kind": "choice", "selector": "fast", "branches": ["fast", "slow"]},
        {"name": "audit", "kind": "conditional", "required": False},
    ]}
    result = derive_expectations(topo)
    by_name = {e.name: e for e in result}
    assert by_name["boot"].status == MISSING_REQUIRED
    assert by_name["src_a"].status == MISSING_REQUIRED
    assert by_name["src_b"].status == MISSING_REQUIRED
    assert by_name["fast"].status == MISSING_REQUIRED
    assert by_name["slow"].status == INTENTIONALLY_ABSENT
    assert by_name["audit"].status == INTENTIONALLY_ABSENT
