# BCLAW4 Communication-Computation Loop

Branch: bclaw4-chaos-lab-001
Experiment: 003
Date: 2026-05-15

## Design Principle

Agent communication is not just logging — it is deterministic computational input.
The same transcript that records what agents said also drives what agents compute.

## Phases

```
Phase 1 — Communication
  proposal  (agent_a → broadcast)
  critique  (agent_b → agent_a, parent=proposal, refs=[proposal])
  arbiter   (arbiter → broadcast, parent=critique, refs=[critique, proposal])

Phase 2 — Computation
  replay ledger → compute_transcript_score(events)
  score = {message_count, critique_count, unresolved_count, arbitration_status}
  append system event (content = canonical_json(score), parent=arbiter)

Phase 3 — Verification
  replay full ledger → 4 events
  verify_ledger → chain_ok=True
  summary_id = "ccl_" + sha256(canonical({run_id, event_count, score, result_message_id}))[:24]
```

## Score Invariants

- `message_count` = total comm events fed to compute (excludes the system event itself)
- `critique_count` = events with role=="critique"
- `unresolved_count` = critiques whose message_id is NOT in any arbiter's references list
- `arbitration_status` = "complete" if any arbiter event exists, else "pending"

## Determinism

- Fixed timestamps per event slot (no runtime clocks)
- compute_transcript_score is order-independent (set-based, aggregate only)
- summary_id excludes ledger_path (varies per run) and LedgerWriter timestamps
