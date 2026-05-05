# BCLAW2

**Status:** Deterministic tested scaffold

## Verified Layers

- **schema** — `schema_def.json` defines required fields and types
- **validator** — validates records against schema; supports strict mode
- **fusion** — deduplicates by id, marks records fused; supports keep_first / keep_last strategies and conflict detection
- **dynamics** — pass-through
- **orchestrator** — runs validation → fusion → dynamics; supports strict, strategy, and no_duplicates flags

## Running Tests

```
python test_phase1.py && python test_fusion.py && python test_dynamics.py && python test_orchestrator.py
```

## Verified Behavior

See [CONTRACT.md](CONTRACT.md) for the authoritative record of all verified behaviors.

## Version

See [VERSION](VERSION) — current baseline is `v2.8`.

See [IMPROVEMENT_LOOP.md](IMPROVEMENT_LOOP.md) for the current improvement loop structure and RSI boundary.
See [EVALUATION.md](EVALUATION.md) for the current evaluation layer status and future direction.

## Test Policy

Do not add new tests unless new behavior or a new contract rule is introduced. Continue running the full test suite (`python test_phase1.py && python test_fusion.py && python test_dynamics.py && python test_orchestrator.py`) after every change.
See [AGENT_RULES.md](AGENT_RULES.md) for agent behavior constraints within this system.

See [guard.py](guard.py) for mechanical enforcement of agent scope constraints (used alongside [AGENT_RULES.md](AGENT_RULES.md)).
All agent actions are validated by [guard.py](guard.py) before execution.
See [AGENT_CANDIDATE.md](AGENT_CANDIDATE.md) for the contract governing how agent outputs become candidate records for BCLAW2 evaluation.

## Candidate Layer Status

The candidate layer is complete and validated:
- `AGENT_CANDIDATE.md` — contract defining required fields and lifecycle
- `candidate_validator.py` — mechanical validation of all required fields
- `agent_candidates_examples.py` — golden examples (valid and invalid), fixture-isolated from pipeline modules

A non-blocking dry-run `candidate_validation` hook is present in the orchestrator summary (`return_summary=True` + `candidates=[...]`). Full pipeline integration with candidate-gating is not yet implemented.
