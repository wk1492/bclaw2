"""
Static topology contract: derive deterministic expectations from a topology document.

Pure functions only. No I/O. No caches. No global state. No mutation of inputs.

A topology document describes a workflow as an ordered list of stages. Each stage
has a kind that determines how its expectations are derived:

    sequential  — one MISSING_REQUIRED expectation for the stage itself
    parallel    — MISSING_REQUIRED for every branch (all must run)
    choice      — selector=None: all branches are MISSING_CONDITIONAL_PENDING_SELECTOR
                  selector=X:   branch X is MISSING_REQUIRED, others are
                                INTENTIONALLY_ABSENT_UNSELECTED_BRANCH
    conditional — required=True: MISSING_REQUIRED; required=False: INTENTIONALLY_ABSENT_UNSELECTED_BRANCH

Validation errors (raised as ValueError before any expectations are produced):
    - duplicate stage name
    - duplicate branch name within a stage
    - choice stage selector names a branch not present in branches list
    - negative retry count
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ExpectationStatus(str, Enum):
    MISSING_REQUIRED = "MISSING_REQUIRED"
    MISSING_CONDITIONAL_PENDING_SELECTOR = "MISSING_CONDITIONAL_PENDING_SELECTOR"
    INTENTIONALLY_ABSENT_UNSELECTED_BRANCH = "INTENTIONALLY_ABSENT_UNSELECTED_BRANCH"


@dataclass(frozen=True)
class StageExpectation:
    name: str
    status: ExpectationStatus
    reason: str = ""


def _validate_stages(stages: list[dict]) -> None:
    seen_names: set[str] = set()
    for stage in stages:
        name = stage["name"]
        if name in seen_names:
            raise ValueError(f"duplicate stage name: {name!r}")
        seen_names.add(name)

        retry = stage.get("retry", 0)
        if not isinstance(retry, int) or retry < 0:
            raise ValueError(f"stage {name!r}: retry must be a non-negative int, got {retry!r}")

        branches = stage.get("branches", [])
        seen_branches: set[str] = set()
        for b in branches:
            if b in seen_branches:
                raise ValueError(f"stage {name!r}: duplicate branch {b!r}")
            seen_branches.add(b)

        if stage.get("kind") == "choice":
            selector = stage.get("selector")
            if selector is not None and selector not in seen_branches:
                raise ValueError(
                    f"stage {name!r}: selector {selector!r} not in branches {sorted(seen_branches)}"
                )


def derive_expectations(topology: dict) -> tuple[StageExpectation, ...]:
    """
    Derive static expectations from a topology document.

    Returns a tuple of StageExpectation in document order (branches within a stage
    are sorted alphabetically for determinism). Never returns None.

    Does not mutate the topology argument. Does not access the filesystem.
    Raises ValueError for structural violations.
    """
    stages = copy.deepcopy(topology.get("stages", []))
    _validate_stages(stages)

    expectations: list[StageExpectation] = []

    for stage in stages:
        name = stage["name"]
        kind = stage.get("kind", "sequential")

        if kind == "sequential":
            expectations.append(StageExpectation(
                name=name,
                status=ExpectationStatus.MISSING_REQUIRED,
                reason="sequential stage",
            ))

        elif kind == "parallel":
            for branch in sorted(stage.get("branches", [])):
                expectations.append(StageExpectation(
                    name=branch,
                    status=ExpectationStatus.MISSING_REQUIRED,
                    reason=f"parallel branch of {name!r}",
                ))

        elif kind == "choice":
            selector = stage.get("selector")
            for branch in sorted(stage.get("branches", [])):
                if selector is None:
                    status = ExpectationStatus.MISSING_CONDITIONAL_PENDING_SELECTOR
                    reason = f"choice branch of {name!r}: selector not set"
                elif branch == selector:
                    status = ExpectationStatus.MISSING_REQUIRED
                    reason = f"selected branch of {name!r}"
                else:
                    status = ExpectationStatus.INTENTIONALLY_ABSENT_UNSELECTED_BRANCH
                    reason = f"unselected branch of {name!r}: selector={selector!r}"
                expectations.append(StageExpectation(name=branch, status=status, reason=reason))

        elif kind == "conditional":
            required = stage.get("required", True)
            expectations.append(StageExpectation(
                name=name,
                status=(
                    ExpectationStatus.MISSING_REQUIRED if required
                    else ExpectationStatus.INTENTIONALLY_ABSENT_UNSELECTED_BRANCH
                ),
                reason=f"conditional stage ({'required' if required else 'not required'})",
            ))

    return tuple(expectations)


def canonical_expectations(expectations: tuple[StageExpectation, ...]) -> str:
    """Canonical JSON serialization of an expectations tuple — byte-stable across runs."""
    return json.dumps(
        [{"name": e.name, "reason": e.reason, "status": e.status.value} for e in expectations],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
