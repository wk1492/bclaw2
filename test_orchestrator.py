# BCLAW2 Phase 4 - Orchestrator Tests
from orchestrator import run_pipeline
from fusion import fuse
from dynamics import apply_dynamics
from worked_example import EXAMPLE_VALID

def test_pipeline_passthrough():
    records = [EXAMPLE_VALID]
    result = run_pipeline(records)
    assert result[0]["id"] == EXAMPLE_VALID["id"]
    assert result[0]["value"] == EXAMPLE_VALID["value"]
    assert result[0]["fused"] is True
    assert "conflict" not in result[0]

def test_pipeline_two_records():
    r1 = {"id": "x1", "value": 10}
    r2 = {"id": "x2", "value": 20}
    result = run_pipeline([r1, r2])
    assert len(result) == 2
    assert result[0]["id"] == "x1"
    assert result[1]["id"] == "x2"
    assert all(r["fused"] is True for r in result)
    assert "conflict" not in result[0]
    assert "conflict" not in result[1]

def test_pipeline_duplicate_id_keep_first():
    r1 = {"id": "dup", "value": 100}
    r2 = {"id": "dup", "value": 200}
    result = run_pipeline([r1, r2])
    assert len(result) == 1
    assert result[0]["value"] == 100
    assert result[0]["fused"] is True
    assert result[0]["conflict"] is True

def test_pipeline_rejects_invalid_record():
    invalid = {"id": "x", "value": "not-a-number"}
    try:
        run_pipeline([EXAMPLE_VALID, invalid])
        assert False, "expected ValueError"
    except ValueError:
        pass

def test_pipeline_strict_rejects_extra_field():
    record = {**EXAMPLE_VALID, "extra": "field"}
    try:
        run_pipeline([record], strict=True)
        assert False, "expected ValueError"
    except ValueError:
        pass

def test_pipeline_keep_last():
    r1 = {"id": "dup", "value": 100}
    r2 = {"id": "dup", "value": 200}
    result = run_pipeline([r1, r2], strategy="keep_last")
    assert len(result) == 1
    assert result[0]["value"] == 200
    assert result[0]["fused"] is True
    assert result[0]["conflict"] is True

def test_pipeline_no_duplicates_raises():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    try:
        run_pipeline([r1, r2], no_duplicates=True)
        assert False, "expected ValueError"
    except ValueError:
        pass

def test_pipeline_return_summary():
    r1 = {"id": "a", "value": 1}
    r2 = {"id": "a", "value": 2}
    r3 = {"id": "b", "value": 3}
    result, summary = run_pipeline([r1, r2, r3], return_summary=True)
    assert summary["input_count"] == 3
    assert summary["output_count"] == 2
    assert summary["duplicate_detected"] is True
    assert summary["strategies_differ"] is False
    assert summary["conflict_count"] == 1

def test_pipeline_summary_conflict_count():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    r3 = {"id": "unique", "value": 3}
    _, summary_with = run_pipeline([r1, r2, r3], return_summary=True)
    assert summary_with["conflict_count"] == 1
    _, summary_without = run_pipeline([r3], return_summary=True)
    assert summary_without["conflict_count"] == 0

def test_pipeline_summary_strategies_differ():
    r1 = {"id": "dup", "value": 100}
    r2 = {"id": "dup", "value": 200}
    result, summary = run_pipeline([r1, r2], compare_strategies=True, return_summary=True)
    assert summary["strategies_differ"] is True

def test_pipeline_compare_strategies_outputs_differ():
    r1 = {"id": "dup", "value": 100}
    r2 = {"id": "dup", "value": 200}
    result, comparison = run_pipeline([r1, r2], compare_strategies=True)
    assert comparison["outputs_differ"] is True
    assert comparison["keep_first_output"][0]["value"] == 100
    assert comparison["keep_last_output"][0]["value"] == 200

def test_pipeline_summary_conflict_ids():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    r3 = {"id": "unique", "value": 3}
    _, summary_with = run_pipeline([r1, r2, r3], return_summary=True)
    assert summary_with["conflict_ids"] == ["dup"]
    _, summary_without = run_pipeline([r3], return_summary=True)
    assert summary_without["conflict_ids"] == []

def test_pipeline_summary_conflict_map():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    r3 = {"id": "unique", "value": 3}
    _, summary_with = run_pipeline([r1, r2, r3], return_summary=True)
    assert summary_with["conflict_map"] == {"dup": 2}
    _, summary_without = run_pipeline([r3], return_summary=True)
    assert summary_without["conflict_map"] == {}

def test_pipeline_summary_evaluation_input():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    _, summary = run_pipeline([r1, r2], compare_strategies=True, return_summary=True)
    ei = summary["evaluation_input"]
    assert ei["strategies_compared"] is True
    assert ei["outputs_differ"] is True
    assert ei["conflict_count"] == 1
    assert ei["conflict_ids"] == ["dup"]
    _, summary2 = run_pipeline([{"id": "x", "value": 1}], return_summary=True)
    ei2 = summary2["evaluation_input"]
    assert ei2["strategies_compared"] is False
    assert ei2["outputs_differ"] is False
    assert ei2["conflict_count"] == 0
    assert ei2["conflict_ids"] == []

def test_pipeline_summary_evaluation_snapshot():
    r1 = {"id": "a", "value": 1}
    r2 = {"id": "b", "value": 2}
    result, summary = run_pipeline([r1, r2], return_summary=True)
    snap = summary["evaluation_snapshot"]
    assert snap["input_records"] == [r1, r2]
    assert snap["output_records"] == result
    assert "evaluation_input" in snap

def test_pipeline_evaluation_triggered():
    r1 = {"id": "a", "value": 1}
    _, summary_on = run_pipeline([r1], return_summary=True, enable_evaluation=True)
    assert summary_on["evaluation_triggered"] is True
    _, summary_off = run_pipeline([r1], return_summary=True, enable_evaluation=False)
    assert summary_off["evaluation_triggered"] is False

def test_pipeline_evaluation_result():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    _, summary_on = run_pipeline([r1, r2], return_summary=True, enable_evaluation=True)
    er = summary_on["evaluation_result"]
    assert er["status"] == "evaluated"
    assert er["outputs_differ"] == summary_on["evaluation_input"]["outputs_differ"]
    assert er["conflict_count"] == summary_on["conflict_count"]
    _, summary_off = run_pipeline([r1], return_summary=True, enable_evaluation=False)
    assert "evaluation_result" not in summary_off

def test_pipeline_evaluation_consistency_check():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    _, summary = run_pipeline([r1, r2], return_summary=True, enable_evaluation=True)
    assert summary["evaluation_result"]["consistency_check"] is True

def test_pipeline_evaluation_details():
    r1 = {"id": "a", "value": 1}
    _, summary = run_pipeline([r1], return_summary=True, enable_evaluation=True, strategy="keep_first")
    ed = summary["evaluation_result"]["evaluation_details"]
    assert ed["strategy_used"] == "keep_first"
    assert ed["compared"] is False

def test_pipeline_evaluation_comparison():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    _, summary = run_pipeline([r1, r2], compare_strategies=True, return_summary=True, enable_evaluation=True)
    ec = summary["evaluation_comparison"]
    assert "keep_first" in ec
    assert "keep_last" in ec
    assert ec["keep_first"]["evaluation_details"]["strategy_used"] == "keep_first"
    assert ec["keep_last"]["evaluation_details"]["strategy_used"] == "keep_last"
    assert ec["keep_first"]["status"] == "evaluated"
    assert ec["keep_last"]["status"] == "evaluated"

def test_pipeline_preferred_strategy():
    # duplicate ids → outputs differ → preferred_strategy = "keep_first"
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    _, s = run_pipeline([r1, r2], compare_strategies=True, return_summary=True, enable_evaluation=True)
    assert s["evaluation_comparison"]["preferred_strategy"] == "keep_first"
    # unique ids → outputs identical → preferred_strategy = null
    r3 = {"id": "a", "value": 1}
    r4 = {"id": "b", "value": 2}
    _, s2 = run_pipeline([r3, r4], compare_strategies=True, return_summary=True, enable_evaluation=True)
    assert s2["evaluation_comparison"]["preferred_strategy"] is None

def test_pipeline_apply_preference():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    first_out = apply_dynamics(fuse([r1, r2], strategy="keep_first"))
    result, _ = run_pipeline(
        [r1, r2],
        compare_strategies=True, return_summary=True,
        enable_evaluation=True, apply_preference=True
    )
    assert result == first_out, f"expected keep_first output, got {result}"

def test_pipeline_preference_applied():
    # duplicate ids → outputs differ → preference applied
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    _, s = run_pipeline([r1, r2], compare_strategies=True, return_summary=True,
                        enable_evaluation=True, apply_preference=True)
    assert s["preference_applied"] is True
    # unique ids → outputs identical → preference not applied
    r3 = {"id": "a", "value": 1}
    r4 = {"id": "b", "value": 2}
    _, s2 = run_pipeline([r3, r4], compare_strategies=True, return_summary=True,
                         enable_evaluation=True, apply_preference=True)
    assert s2["preference_applied"] is False

def test_pipeline_override_strategy():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    last_out = apply_dynamics(fuse([r1, r2], strategy="keep_last"))
    result, _ = run_pipeline(
        [r1, r2],
        compare_strategies=True, return_summary=True,
        enable_evaluation=True, apply_preference=True,
        override_strategy="keep_last"
    )
    assert result == last_out, f"expected keep_last output, got {result}"

def test_pipeline_execution_mode():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    # default
    _, s = run_pipeline([r1, r2], return_summary=True)
    assert s["execution_mode"] == "default"
    # preferred
    _, s = run_pipeline([r1, r2], compare_strategies=True, return_summary=True,
                        enable_evaluation=True, apply_preference=True)
    assert s["execution_mode"] == "preferred"
    # override
    _, s = run_pipeline([r1, r2], compare_strategies=True, return_summary=True,
                        enable_evaluation=True, apply_preference=True, override_strategy="keep_last")
    assert s["execution_mode"] == "override"

def test_pipeline_evaluation_rationale():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    _, s = run_pipeline([r1, r2], compare_strategies=True, return_summary=True, enable_evaluation=True)
    assert s["evaluation_comparison"]["rationale"] == "keep_first selected due to deterministic rule when outputs differ"
    r3 = {"id": "a", "value": 1}
    r4 = {"id": "b", "value": 2}
    _, s2 = run_pipeline([r3, r4], compare_strategies=True, return_summary=True, enable_evaluation=True)
    assert s2["evaluation_comparison"]["rationale"] == "no preference applied because outputs are identical"

def test_pipeline_comparison_summary():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    _, s = run_pipeline([r1, r2], compare_strategies=True, return_summary=True, enable_evaluation=True)
    assert s["evaluation_comparison"]["comparison_summary"] == "strategies produce different outputs"
    r3 = {"id": "a", "value": 1}
    r4 = {"id": "b", "value": 2}
    _, s2 = run_pipeline([r3, r4], compare_strategies=True, return_summary=True, enable_evaluation=True)
    assert s2["evaluation_comparison"]["comparison_summary"] == "strategies produce identical outputs"

def test_pipeline_difference_detail():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    _, s = run_pipeline([r1, r2], compare_strategies=True, return_summary=True, enable_evaluation=True)
    assert s["evaluation_comparison"]["difference_detail"] == "outputs differ in at least one field"
    r3 = {"id": "a", "value": 1}
    r4 = {"id": "b", "value": 2}
    _, s2 = run_pipeline([r3, r4], compare_strategies=True, return_summary=True, enable_evaluation=True)
    assert s2["evaluation_comparison"]["difference_detail"] == "no differences between outputs"

def test_pipeline_preference_policy():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    last_out = apply_dynamics(fuse([r1, r2], strategy="keep_last"))
    result, summary = run_pipeline(
        [r1, r2],
        compare_strategies=True, return_summary=True,
        enable_evaluation=True, apply_preference=True,
        preference_policy="keep_last"
    )
    assert summary["evaluation_comparison"]["preferred_strategy"] == "keep_last"
    assert result == last_out

def test_pipeline_prefer_consistent_policy():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    _, summary = run_pipeline(
        [r1, r2],
        compare_strategies=True, return_summary=True,
        enable_evaluation=True, preference_policy="prefer_consistent"
    )
    assert summary["evaluation_comparison"]["preferred_strategy"] == "keep_first"
    assert summary["evaluation_comparison"]["rationale"] == "prefer_consistent selected first output due to deterministic consistency rule"

def test_pipeline_invalid_policy_raises():
    r1 = {"id": "a", "value": 1}
    try:
        run_pipeline([r1], preference_policy="invalid_policy")
        assert False, "expected ValueError"
    except ValueError:
        pass

def test_pipeline_prefer_lower_conflict_policy():
    # Both strategies produce same conflict_count (1 each) → fallback to keep_first
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    _, summary = run_pipeline(
        [r1, r2],
        compare_strategies=True, return_summary=True,
        enable_evaluation=True, preference_policy="prefer_lower_conflict"
    )
    ec = summary["evaluation_comparison"]
    assert ec["preferred_strategy"] == "keep_first"
    assert "prefer_lower_conflict" in ec["rationale"] or "fallback" in ec["rationale"]

def test_pipeline_divergence_detected():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    _, s = run_pipeline([r1, r2], compare_strategies=True, return_summary=True, enable_evaluation=True)
    assert s["evaluation_comparison"]["divergence_detected"] is True
    r3 = {"id": "a", "value": 1}
    r4 = {"id": "b", "value": 2}
    _, s2 = run_pipeline([r3, r4], compare_strategies=True, return_summary=True, enable_evaluation=True)
    assert s2["evaluation_comparison"]["divergence_detected"] is False

def test_pipeline_prefer_lower_conflict_no_divergence():
    r1 = {"id": "a", "value": 1}
    r2 = {"id": "b", "value": 2}
    _, summary = run_pipeline(
        [r1, r2],
        compare_strategies=True, return_summary=True,
        enable_evaluation=True, preference_policy="prefer_lower_conflict"
    )
    assert summary["evaluation_comparison"]["preferred_strategy"] is None
    assert "no meaningful divergence" in summary["evaluation_comparison"]["rationale"]

def test_pipeline_losing_strategy_reason():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    # preferred = keep_first (default policy) → losing = keep_last
    _, s = run_pipeline([r1, r2], compare_strategies=True, return_summary=True, enable_evaluation=True)
    assert s["evaluation_comparison"]["losing_strategy_reason"] == "keep_last not selected based on policy conditions"
    # preferred = keep_last
    _, s2 = run_pipeline([r1, r2], compare_strategies=True, return_summary=True,
                         enable_evaluation=True, preference_policy="keep_last")
    assert s2["evaluation_comparison"]["losing_strategy_reason"] == "keep_first not selected based on policy conditions"
    # preferred = None (no divergence)
    r3 = {"id": "a", "value": 1}
    r4 = {"id": "b", "value": 2}
    _, s3 = run_pipeline([r3, r4], compare_strategies=True, return_summary=True, enable_evaluation=True)
    assert s3["evaluation_comparison"]["losing_strategy_reason"] == "no strategy selected due to no meaningful divergence"

def test_pipeline_preference_strength():
    r1 = {"id": "dup", "value": 1}
    r2 = {"id": "dup", "value": 2}
    # diverged + equal conflict_count → moderate
    _, s = run_pipeline([r1, r2], compare_strategies=True, return_summary=True, enable_evaluation=True)
    assert s["evaluation_comparison"]["preference_strength"] == "moderate"
    # no divergence → preferred=None → none
    r3 = {"id": "a", "value": 1}
    r4 = {"id": "b", "value": 2}
    _, s2 = run_pipeline([r3, r4], compare_strategies=True, return_summary=True, enable_evaluation=True)
    assert s2["evaluation_comparison"]["preference_strength"] == "none"
    # prefer_lower_conflict no divergence → preferred=None → none (already covered)
    # weak: divergence_detected=False but preferred not None — not reachable with current logic;
    # confirm moderate is the active diverged case
    assert s["evaluation_comparison"]["divergence_detected"] is True

def test_pipeline_candidate_validation():
    r1 = {"id": "a", "value": 1}
    valid_c = {
        "id": "cand_001", "source_model": "claude-sonnet", "task_id": "t1",
        "proposed_action": "add field", "rationale": "needed", "evidence": "test",
        "risk_notes": "none", "status": "proposed",
    }
    invalid_c = {"id": "cand_002", "source_model": "gpt-4o"}  # missing fields
    _, summary = run_pipeline([r1], return_summary=True, candidates=[valid_c, invalid_c])
    cv = summary["candidate_validation"]
    assert cv[0] == {"id": "cand_001", "valid": True}
    assert cv[1]["id"] == "cand_002"
    assert cv[1]["valid"] is False
    assert "reason" in cv[1]

if __name__ == "__main__":
    test_pipeline_passthrough()
    print("PASS: orchestrator pipeline pass-through verified, no conflict")
    test_pipeline_two_records()
    print("PASS: orchestrator two-record order and contents unchanged, no conflict")
    test_pipeline_duplicate_id_keep_first()
    print("PASS: orchestrator duplicate ids — first record kept, conflict=True")
    test_pipeline_rejects_invalid_record()
    print("PASS: orchestrator rejects pipeline with invalid record")
    test_pipeline_strict_rejects_extra_field()
    print("PASS: orchestrator strict mode rejects record with extra field")
    test_pipeline_keep_last()
    print("PASS: orchestrator keep_last — last record kept, conflict=True")
    test_pipeline_no_duplicates_raises()
    print("PASS: orchestrator no_duplicates=True raises on duplicate id")
    test_pipeline_compare_strategies_outputs_differ()
    print("PASS: orchestrator compare_strategies=True — outputs_differ=True verified")
    test_pipeline_return_summary()
    print("PASS: orchestrator return_summary=True returns correct summary with strategies_differ=False")
    test_pipeline_summary_strategies_differ()
    print("PASS: orchestrator summary strategies_differ=True when compare_strategies=True")
    test_pipeline_summary_conflict_count()
    print("PASS: orchestrator summary conflict_count correct for dup and unique inputs")
    test_pipeline_summary_conflict_ids()
    print("PASS: orchestrator summary conflict_ids correct for dup and unique inputs")
    test_pipeline_summary_conflict_map()
    print("PASS: orchestrator summary conflict_map correct for dup and unique inputs")
    test_pipeline_summary_evaluation_input()
    print("PASS: orchestrator summary evaluation_input fields verified")
    test_pipeline_summary_evaluation_snapshot()
    print("PASS: orchestrator summary evaluation_snapshot contains correct input/output refs")
    test_pipeline_evaluation_triggered()
    print("PASS: orchestrator evaluation_triggered=True/False verified")
    test_pipeline_evaluation_result()
    print("PASS: orchestrator evaluation_result status=evaluated, values match signals")
    test_pipeline_evaluation_consistency_check()
    print("PASS: orchestrator evaluation_result consistency_check=True verified")
    test_pipeline_evaluation_details()
    print("PASS: orchestrator evaluation_result evaluation_details fields verified")
    test_pipeline_evaluation_comparison()
    print("PASS: orchestrator evaluation_comparison both strategies present and evaluated")
    test_pipeline_preferred_strategy()
    print("PASS: orchestrator evaluation_comparison preferred_strategy verified")
    test_pipeline_apply_preference()
    print("PASS: orchestrator apply_preference=True returns keep_first output")
    test_pipeline_preference_applied()
    print("PASS: orchestrator preference_applied=True/False verified")
    test_pipeline_override_strategy()
    print("PASS: orchestrator override_strategy=keep_last returns keep_last output")
    test_pipeline_execution_mode()
    print("PASS: orchestrator execution_mode default/preferred/override verified")
    test_pipeline_evaluation_rationale()
    print("PASS: orchestrator evaluation_comparison rationale verified")
    test_pipeline_comparison_summary()
    print("PASS: orchestrator evaluation_comparison comparison_summary verified")
    test_pipeline_difference_detail()
    print("PASS: orchestrator evaluation_comparison difference_detail verified")
    test_pipeline_preference_policy()
    print("PASS: orchestrator preference_policy=keep_last sets preferred_strategy and returns keep_last output")
    test_pipeline_prefer_consistent_policy()
    print("PASS: orchestrator preference_policy=prefer_consistent yields keep_first with correct rationale")
    test_pipeline_invalid_policy_raises()
    print("PASS: orchestrator invalid preference_policy raises ValueError")
    test_pipeline_prefer_lower_conflict_policy()
    print("PASS: orchestrator preference_policy=prefer_lower_conflict selects correctly")
    test_pipeline_divergence_detected()
    print("PASS: orchestrator evaluation_comparison divergence_detected verified")
    test_pipeline_prefer_lower_conflict_no_divergence()
    print("PASS: orchestrator prefer_lower_conflict no-divergence yields preferred_strategy=None")
    test_pipeline_losing_strategy_reason()
    print("PASS: orchestrator evaluation_comparison losing_strategy_reason all three cases verified")
    test_pipeline_preference_strength()
    print("PASS: orchestrator evaluation_comparison preference_strength cases verified")
    test_pipeline_candidate_validation()
    print("PASS: orchestrator candidate_validation dry-run: valid and invalid candidates reported correctly")

def test_orchestrator_candidate_validation_repeatability():
    from orchestrator import run_pipeline
    from worked_example import EXAMPLE_VALID
    from agent_candidates_examples import (
        EXAMPLE_AGENT_CANDIDATE_VALID,
        EXAMPLE_AGENT_CANDIDATE_INVALID_MISSING_STATUS,
    )

    candidates = [
        EXAMPLE_AGENT_CANDIDATE_VALID,
        EXAMPLE_AGENT_CANDIDATE_INVALID_MISSING_STATUS,
    ]

    _, summary_1 = run_pipeline([EXAMPLE_VALID], return_summary=True, candidates=candidates)
    _, summary_2 = run_pipeline([EXAMPLE_VALID], return_summary=True, candidates=candidates)

    assert summary_1["candidate_validation"] == summary_2["candidate_validation"]
