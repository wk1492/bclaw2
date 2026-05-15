"""
Deterministic epistemic state diff — pure function, no side effects.

Shallow comparison of two plain dicts. Output is constructed in sorted key
order so that json.dumps(result, sort_keys=True, separators=(",", ":"))
produces byte-identical output for identical inputs across all runs.
"""
from __future__ import annotations


def diff_epistemic_state(before: dict, after: dict) -> dict:
    """
    Shallow diff of two epistemic state dicts.

    Returns:
        {
            "added":   {k: v}                        keys in after, absent in before
            "removed": {k: v}                        keys in before, absent in after
            "changed": {k: {"before": v, "after": v}}  keys in both with differing values
        }

    Pure function. Inputs are never mutated.
    Output dicts are built in sorted key order for determinism.
    """
    before_keys = set(before)
    after_keys = set(after)

    added = {k: after[k] for k in sorted(after_keys - before_keys)}
    removed = {k: before[k] for k in sorted(before_keys - after_keys)}
    changed = {
        k: {"before": before[k], "after": after[k]}
        for k in sorted(before_keys & after_keys)
        if before[k] != after[k]
    }

    return {"added": added, "removed": removed, "changed": changed}
