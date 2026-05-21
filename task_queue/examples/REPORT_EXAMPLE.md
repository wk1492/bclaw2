# Report Examples

Three canonical examples of bounded cycle reports.

---

## Example 1 — Successful docs-only cycle

Task: Add deterministic operator reporting contract docs.

```
HEAD:    8edc0da
TESTS:   871 passed
FILES:   task_queue/README.md, task_queue/REPORT_FORMAT.md, task_queue/examples/REPORT_EXAMPLE.md
PUSHED:  no
RISKS:   none
```

---

## Example 2 — Successful code + tests cycle

Task: Fix serialization and ordering violations found in determinism audit.

```
HEAD:    8edc0da
TESTS:   871 passed
FILES:   execution_ledger.py, fusion.py, safe_patcher.py, transcript_validator.py, bclaw4_mailbox.py, test_bclaw4_mailbox.py
PUSHED:  no
RISKS:   D1 deferred — ledger_writer timestamp-in-hash requires migration; all known callers supply deterministic timestamps
NOTES:   deferred D1 migration — requires fixture regeneration before addressing
```

---

## Example 3 — Bounded failure-stop

Task: Exclude timestamp from ledger event_hash to harden replay determinism.

```
HEAD:    none
TESTS:   868 passed, 3 failed — test_golden_worked_example::test_replay_verify
FILES:   ledger_writer.py (reverted)
PUSHED:  no
RISKS:   hash-scheme migration breaks on-disk fixtures; existing execution_ledger.jsonl invalidated
BLOCKERS: fix requires fixture regeneration and migration versioning; exceeds single-cycle scope
```

---

## Notes on these examples

- Example 1 shows a clean docs-only cycle: no test risk, no code changes.
- Example 2 shows a multi-file code cycle with a deferred finding noted in NOTES.
- Example 3 shows a failure-stop: the fix was attempted, caused failures, was reverted, and the cycle halted cleanly. The BLOCKERS field explains why the cycle did not proceed.

All three examples conform to REPORT_FORMAT.md:
- Canonical field order (HEAD, TESTS, FILES, PUSHED, RISKS)
- One line per field
- Deterministic language
- No speculation, no roadmap items
