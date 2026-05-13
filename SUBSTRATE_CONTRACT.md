# Substrate Contract

**SUBSTRATE_VERSION:** 1
**Date:** 2026-05-13
**Modules:** `substrate_errors.py`, `substrate_contract.py`

---

## 1. Scope

This contract names and freezes the observable error behavior of the deterministic
transcript substrate at version 1. It does not change replay ordering, hashing,
append semantics, validation messages, topology behavior, or baseline artifacts.

---

## 2. Storage Format

The substrate uses append-only JSONL (one JSON object per line, UTF-8 encoded).
Each line is terminated by a single LF (`\n`). The file must end with a final LF.
No CRLF line endings. No blank lines between records.

read-only verification (`substrate_verify_ledger`) re-derives all hashes from
stored content and reports failures without mutating the ledger.

---

## 3. Hash-Chain Semantics

Every appended record carries:
- `event_hash` — sha256 of the record payload (excluding chain fields)
- `rolling_hash` — sha256 of `previous_rolling_hash + event_hash`
- `previous_hash` — the rolling hash of the preceding record (genesis: 64 zeros)

canonical JSON serialization for all hash inputs:
```python
json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

---

## 4. Error Code Taxonomy

The following stable constants are defined in `substrate_errors.py`.
Human-readable failure strings from the underlying modules are preserved unchanged;
these codes are layered on top as additional structure.

| Code | Trigger |
|---|---|
| `E_DUPLICATE_MESSAGE_ID` | `append_transcript_event` called with a `message_id` already present in the ledger |
| `E_MISSING_PARENT` | `append_transcript_event` called with a `parent_message_id` not present in the ledger |
| `E_PREVIOUS_HASH_MISMATCH` | A record's `previous_hash` does not match the prior record's `rolling_hash` |
| `E_INVALID_JSON` | A ledger line cannot be parsed as JSON (truncated or corrupt) |
| `E_MISSING_FINAL_NEWLINE` | The ledger file does not end with a final LF terminator |

### 4.1 Exception codes

`substrate_append_transcript_event` re-raises `TranscriptValidationError` unchanged
but attaches `.code` when the error maps to a known constant. The exception message
text is never modified.

### 4.2 Verification codes

`substrate_verify_ledger` returns the full `verify_ledger` result dict with one
additional key:

```
error_codes: list[str]   — substrate error constants for each failure in failures[]
```

All existing keys (`ok`, `count`, `failures`, `last_rolling_hash`) are preserved
and their values are not altered.

---

## 5. Compatibility Guarantees

The following changes require a new `SUBSTRATE_VERSION`. Any implementation that
introduces one of these changes without incrementing the version number is in
violation of this contract:

- changing canonical JSON serialization
- changing hash algorithm
- changing line termination requirements
- changing replay ordering semantics
- changing append validation semantics
- changing rolling hash derivation
- changing meaning of existing error codes

Additive changes — new error codes, new optional result keys, new wrapper functions —
do not require a version increment provided they do not alter any of the above.

---

## 6. Preserved Invariants

- `SUBSTRATE_VERSION` is an integer. Version 1 freezes this document.
- No hash input is changed by this contract layer.
- No `message_id` generation is changed.
- No replay ordering is changed.
- No topology behavior is changed.
- No baseline artifact is mutated.
- All error message strings from `transcript_validator`, `transcript_ledger`, and
  `ledger_writer` remain character-for-character identical.

---

## 7. Workspace Identity as Substrate Precondition

### 7.1 Failure mode: coherent-output-on-wrong-lineage

**Definition:** Work produced from the wrong repository, branch, or architectural
lineage that is internally coherent but semantically irrelevant or contaminating to
the BCLAW2 substrate.

**Why it is dangerous:**

- Diffs may look valid and pass code review.
- Tests may pass — but in a different repo with a different schema or orchestrator.
- Commits may be coherent and well-formed but address the wrong codebase.
- Old schemas, orchestrators, or ledger formats from prior projects can silently
  contaminate BCLAW2 data structures, replay semantics, or hash chains.
- The failure is invisible until a frozen baseline hash diverges or a replay
  produces an unexpected result.

**Prevention:**

- Run `./doctor.sh --strict` before any mutation, schema change, orchestration
  change, runner/transcript wiring, or FCM/graph work.
- Verify repo root is exactly `~/Downloads/bclaw2`.
- Verify current branch is `main`.
- Verify required substrate files are present:
  `transcript_event.py`, `transcript_ledger.py`, `transcript_topology.py`,
  `model_runner.py`, `SUBSTRATE_CONTRACT.md`.
- Stop immediately on identity failure. Do not proceed. Run `cd ~/Downloads/bclaw2`
  and re-run `./doctor.sh --strict`.

**Workspace identity is a substrate precondition, not a convenience check.**
A substrate version number is only meaningful relative to the correct lineage.
Work committed from the wrong lineage cannot be reconciled with frozen baseline
artifacts without re-deriving and re-verifying all hashes.
