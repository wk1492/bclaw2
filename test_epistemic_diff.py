"""
Focused tests for diff_epistemic_state.
Covers: no-change, add/remove, changed values, directionality, serialization stability.
"""
import json

from epistemic_diff import diff_epistemic_state


def test_identical_states_produce_empty_diff():
    state = {"claim_a": {"epistemic_status": "proposed"}}
    result = diff_epistemic_state(state, state)
    assert result == {"added": {}, "removed": {}, "changed": {}}


def test_addition_and_removal_detected():
    before = {"claim_a": {"epistemic_status": "proposed"}}
    after  = {"claim_b": {"epistemic_status": "supported"}}
    result = diff_epistemic_state(before, after)
    assert result["added"]   == {"claim_b": {"epistemic_status": "supported"}}
    assert result["removed"] == {"claim_a": {"epistemic_status": "proposed"}}
    assert result["changed"] == {}


def test_changed_value_detected():
    before = {"claim_x": {"epistemic_status": "proposed",  "confidence": 0.5}}
    after  = {"claim_x": {"epistemic_status": "supported", "confidence": 0.5}}
    result = diff_epistemic_state(before, after)
    assert result["changed"]["claim_x"]["before"]["epistemic_status"] == "proposed"
    assert result["changed"]["claim_x"]["after"]["epistemic_status"]  == "supported"
    assert result["added"] == {} and result["removed"] == {}


def test_diff_is_directional():
    before = {"claim_a": {"epistemic_status": "proposed"}}
    after  = {"claim_b": {"epistemic_status": "supported"}}
    fwd = diff_epistemic_state(before, after)
    rev = diff_epistemic_state(after, before)
    assert fwd != rev
    assert fwd["added"]   == rev["removed"]
    assert fwd["removed"] == rev["added"]


def test_serialized_output_is_byte_stable():
    before = {"claim_z": {"confidence": 0.9}, "claim_a": {"confidence": 0.1}}
    after  = {"claim_z": {"confidence": 0.7}, "claim_a": {"confidence": 0.1}}
    opts = dict(sort_keys=True, separators=(",", ":"))
    r1 = diff_epistemic_state(before, after)
    r2 = diff_epistemic_state(before, after)
    assert json.dumps(r1, **opts) == json.dumps(r2, **opts)


# ── Canonical serialization hardening ────────────────────────────────────────

_OPTS = dict(sort_keys=True, separators=(",", ":"))


def test_canonical_stable_across_repeated_runs():
    before = {"claim_a": "x", "claim_b": "y"}
    after  = {"claim_a": "z", "claim_b": "y"}
    results = [json.dumps(diff_epistemic_state(before, after), **_OPTS) for _ in range(6)]
    assert len(set(results)) == 1


def test_canonical_stable_despite_input_insertion_order():
    before_v1 = {"claim_a": "old", "claim_b": "same"}
    before_v2 = {"claim_b": "same", "claim_a": "old"}
    after_v1  = {"claim_a": "new", "claim_b": "same"}
    after_v2  = {"claim_b": "same", "claim_a": "new"}
    s1 = json.dumps(diff_epistemic_state(before_v1, after_v1), **_OPTS)
    s2 = json.dumps(diff_epistemic_state(before_v2, after_v2), **_OPTS)
    assert s1 == s2


def test_canonical_stable_nested_dict_payload():
    before = {"claim_a": {"status": "proposed", "refs": ["r1", "r2"]}}
    after  = {"claim_a": {"status": "supported", "refs": ["r1", "r2"]}}
    r1 = json.dumps(diff_epistemic_state(before, after), **_OPTS)
    r2 = json.dumps(diff_epistemic_state(before, after), **_OPTS)
    assert r1 == r2


def test_canonical_stable_list_payload():
    before = {"claim_a": ["evidence_1", "evidence_2"]}
    after  = {"claim_a": ["evidence_1", "evidence_3"]}
    r1 = json.dumps(diff_epistemic_state(before, after), **_OPTS)
    r2 = json.dumps(diff_epistemic_state(before, after), **_OPTS)
    assert r1 == r2


def test_canonical_stable_none_payload():
    before = {"claim_a": None}
    after  = {"claim_a": "proposed"}
    r1 = json.dumps(diff_epistemic_state(before, after), **_OPTS)
    r2 = json.dumps(diff_epistemic_state(before, after), **_OPTS)
    assert r1 == r2


def test_canonical_stable_bool_payload():
    before = {"claim_a": True}
    after  = {"claim_a": False}
    r1 = json.dumps(diff_epistemic_state(before, after), **_OPTS)
    r2 = json.dumps(diff_epistemic_state(before, after), **_OPTS)
    assert r1 == r2


def test_no_mutation_of_before():
    import copy
    before = {"claim_a": {"status": "proposed"}}
    after  = {"claim_b": {"status": "supported"}}
    snapshot = copy.deepcopy(before)
    diff_epistemic_state(before, after)
    assert before == snapshot


def test_no_mutation_of_after():
    import copy
    before = {"claim_a": {"status": "proposed"}}
    after  = {"claim_b": {"status": "supported"}}
    snapshot = copy.deepcopy(after)
    diff_epistemic_state(before, after)
    assert after == snapshot
