# BCLAW2 Phase 4 - Minimal Orchestrator
from fusion import fuse
from dynamics import apply_dynamics
from validator import validate
from candidate_validator import validate_candidate as _validate_candidate

def run_pipeline(records, strict=False, strategy="keep_first", no_duplicates=False, return_summary=False, compare_strategies=False, enable_evaluation=False, apply_preference=False, override_strategy=None, preference_policy="keep_first", candidates=None):
    _valid_strategies = ("keep_first", "keep_last")
    _valid_policies = ("keep_first", "keep_last", "prefer_consistent", "prefer_lower_conflict")
    if strategy not in _valid_strategies:
        raise ValueError(f"invalid strategy: {strategy!r}; allowed: {_valid_strategies}")
    if override_strategy is not None and override_strategy not in _valid_strategies:
        raise ValueError(f"invalid override_strategy: {override_strategy!r}; allowed: {_valid_strategies} or None")
    if preference_policy not in _valid_policies:
        raise ValueError(f"invalid preference_policy: {preference_policy!r}; allowed: {_valid_policies}")
    for record in records:
        ok, msg = validate(record, strict=strict)
        if not ok:
            raise ValueError(f"invalid record: {msg}")
    if no_duplicates:
        seen = set()
        for record in records:
            if record["id"] in seen:
                raise ValueError(f"duplicate id detected: {record['id']}")
            seen.add(record["id"])
    ids = [r["id"] for r in records]
    duplicate_detected = len(ids) != len(set(ids))
    id_counts = {}
    for i in ids:
        id_counts[i] = id_counts.get(i, 0) + 1
    fused = fuse(records, strategy=strategy)
    result = apply_dynamics(fused)
    conflict_ids_list = [r["id"] for r in result if r.get("conflict") is True]
    conflict_map = {i: id_counts[i] for i in conflict_ids_list}
    if compare_strategies:
        first_out = apply_dynamics(fuse(records, strategy="keep_first"))
        last_out = apply_dynamics(fuse(records, strategy="keep_last"))
        comparison = {
            "keep_first_output": first_out,
            "keep_last_output": last_out,
            "outputs_differ": first_out != last_out,
        }
        strategies_differ = first_out != last_out
        if return_summary:
            eval_input = {
                "strategies_compared": True,
                "outputs_differ": strategies_differ,
                "conflict_count": len(conflict_ids_list),
                "conflict_ids": conflict_ids_list,
            }
            summary = {
                "input_count": len(records),
                "output_count": len(result),
                "duplicate_detected": duplicate_detected,
                "strategies_differ": strategies_differ,
                "conflict_count": len(conflict_ids_list),
                "conflict_ids": conflict_ids_list,
                "conflict_map": conflict_map,
                "evaluation_input": eval_input,
                "evaluation_snapshot": {
                    "input_records": records,
                    "output_records": result,
                    "evaluation_input": eval_input,
                },
                "evaluation_triggered": enable_evaluation,
            }
            if enable_evaluation:
                er = {
                    "status": "evaluated",
                    "outputs_differ": eval_input["outputs_differ"],
                    "conflict_count": len(conflict_ids_list),
                }
                er["consistency_check"] = (
                    er["outputs_differ"] == eval_input["outputs_differ"]
                    and er["conflict_count"] == summary["conflict_count"]
                )
                er["evaluation_details"] = {
                    "strategy_used": strategy,
                    "compared": eval_input["strategies_compared"],
                }
                summary["evaluation_result"] = er
                # Build per-strategy evaluation results
                def _make_er(s, out):
                    first_cids = [r["id"] for r in out if r.get("conflict") is True]
                    e = {
                        "status": "evaluated",
                        "outputs_differ": strategies_differ,
                        "conflict_count": len(first_cids),
                    }
                    e["consistency_check"] = (
                        e["outputs_differ"] == strategies_differ
                        and e["conflict_count"] == len(first_cids)
                    )
                    e["evaluation_details"] = {
                        "strategy_used": s,
                        "compared": True,
                    }
                    return e
                _kf_er = _make_er("keep_first", first_out)
                _kl_er = _make_er("keep_last", last_out)
                if preference_policy == "prefer_lower_conflict" and strategies_differ:
                    kf_cc = _kf_er["conflict_count"]
                    kl_cc = _kl_er["conflict_count"]
                    if kl_cc < kf_cc:
                        _preferred = "keep_last"
                        _rationale = "prefer_lower_conflict selected keep_last due to lower conflict count"
                    else:
                        _preferred = "keep_first"
                        _rationale = "fallback to keep_first due to equal conflict count"
                elif preference_policy == "prefer_lower_conflict" and not strategies_differ:
                    _preferred = None
                    _rationale = "no preference applied because no meaningful divergence detected"
                elif preference_policy == "prefer_consistent" and strategies_differ:
                    _preferred = "keep_first"
                    _rationale = "prefer_consistent selected first output due to deterministic consistency rule"
                elif strategies_differ:
                    _effective_policy = preference_policy if preference_policy in ("keep_first", "keep_last") else "keep_first"
                    _preferred = _effective_policy
                    _rationale = "keep_first selected due to deterministic rule when outputs differ"
                else:
                    _preferred = None
                    _rationale = "no preference applied because outputs are identical"
                _losing_reason = (
                    "keep_last not selected based on policy conditions" if _preferred == "keep_first" else
                    "keep_first not selected based on policy conditions" if _preferred == "keep_last" else
                    "no strategy selected due to no meaningful divergence"
                )
                _kf_cc = _kf_er["conflict_count"]
                _kl_cc = _kl_er["conflict_count"]
                _diverged = first_out != last_out
                if _preferred is None:
                    _strength = "none"
                elif not _diverged:
                    _strength = "weak"
                elif _kf_cc == _kl_cc:
                    _strength = "moderate"
                else:
                    _strength = "strong"
                summary["evaluation_comparison"] = {
                    "keep_first": _kf_er,
                    "keep_last": _kl_er,
                    "preferred_strategy": _preferred,
                    "rationale": _rationale,
                    "comparison_summary": "strategies produce different outputs" if strategies_differ else "strategies produce identical outputs",
                    "difference_detail": "outputs differ in at least one field" if strategies_differ else "no differences between outputs",
                    "divergence_detected": _diverged,
                    "losing_strategy_reason": _losing_reason,
                    "preference_strength": _strength,
                }
            if apply_preference and "evaluation_comparison" in summary:
                ps = override_strategy if override_strategy in ("keep_first", "keep_last") else summary["evaluation_comparison"].get("preferred_strategy")
                if ps == "keep_first":
                    result = first_out
                    summary["preference_applied"] = True
                    summary["execution_mode"] = "override" if override_strategy in ("keep_first", "keep_last") else "preferred"
                elif ps == "keep_last":
                    result = last_out
                    summary["preference_applied"] = True
                    summary["execution_mode"] = "override" if override_strategy in ("keep_first", "keep_last") else "preferred"
                else:
                    summary["preference_applied"] = False
                    summary["execution_mode"] = "preferred"
            elif apply_preference:
                summary["preference_applied"] = False
                summary["execution_mode"] = "preferred"
            else:
                summary["execution_mode"] = "default"
            if candidates:
                _cv = []
                for _c in candidates:
                    try:
                        _validate_candidate(_c)
                        _cv.append({"id": _c["id"], "valid": True})
                    except Exception as _e:
                        _cv.append({"id": _c.get("id", "unknown"), "valid": False, "reason": str(_e)})
                summary["candidate_validation"] = _cv
            return result, summary
        return result, comparison
    if return_summary:
        eval_input = {
            "strategies_compared": False,
            "outputs_differ": False,
            "conflict_count": len(conflict_ids_list),
            "conflict_ids": conflict_ids_list,
        }
        summary = {
            "input_count": len(records),
            "output_count": len(result),
            "duplicate_detected": duplicate_detected,
            "strategies_differ": False,
            "conflict_count": len(conflict_ids_list),
            "conflict_ids": conflict_ids_list,
            "conflict_map": conflict_map,
            "evaluation_input": eval_input,
            "evaluation_snapshot": {
                "input_records": records,
                "output_records": result,
                "evaluation_input": eval_input,
            },
            "evaluation_triggered": enable_evaluation,
        }
        if enable_evaluation:
            er = {
                "status": "evaluated",
                "outputs_differ": eval_input["outputs_differ"],
                "conflict_count": len(conflict_ids_list),
            }
            er["consistency_check"] = (
                er["outputs_differ"] == eval_input["outputs_differ"]
                and er["conflict_count"] == summary["conflict_count"]
            )
            er["evaluation_details"] = {
                "strategy_used": strategy,
                "compared": eval_input["strategies_compared"],
            }
            summary["evaluation_result"] = er
        summary["execution_mode"] = "default"
        if candidates:
            _cv = []
            for _c in candidates:
                try:
                    _validate_candidate(_c)
                    _cv.append({"id": _c["id"], "valid": True})
                except Exception as _e:
                    _cv.append({"id": _c.get("id", "unknown"), "valid": False, "reason": str(_e)})
            summary["candidate_validation"] = _cv
        return result, summary
    return result
