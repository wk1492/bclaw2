# Determinism Audit — BCLAW2

## Summary

No `uuid`, `random`, or `hash()` (Python builtin) usage found. Four classes of nondeterminism were identified.

---

## Finding 1 — Timestamp-based message IDs in `agent_message_schema.py`

**File:** `agent_message_schema.py` lines 31–32  
**Pattern:** `message_id = f"msg_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{agent}_{msg_type[:4]}"`  
**Problem:** Message IDs encode wall-clock time; two calls in the same second produce the same ID, two calls in different seconds produce different IDs.  
**Fix:** `AgentMessage.new()` now accepts an explicit `message_id` parameter. `generate_message_id()` from `deterministic_message_id.py` must be used for all new messages. The validator regex updated to accept `msg_<hex64>` format.

---

## Finding 2 — Timestamp-based candidate IDs in `generate_candidates.py`

**File:** `generate_candidates.py` line 5  
**Pattern:** `base_date = datetime.now(UTC).strftime("%Y%m%d")`  
**Problem:** Candidate IDs include today's date; regenerating on a different date produces different IDs for the same logical candidates.  
**Severity:** Medium. Candidate IDs are used as stable references across ledger events.  
**Fix:** Document as metadata-only timestamp. The date in candidate IDs is for human readability, not identity. Callers that need stable IDs must pass an explicit `base_date` or use fixed seeds.

---

## Finding 3 — Timestamp-based checkpoint IDs in `checkpoint_manager.py`

**File:** `checkpoint_manager.py` line 30  
**Pattern:** `checkpoint_id = checkpoint_id or f"cp_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{checkpoint_type}"`  
**Problem:** Auto-generated checkpoint IDs are time-dependent; replay or re-run will produce different IDs.  
**Severity:** Low. Callers that need stable IDs already pass `checkpoint_id` explicitly.  
**Fix:** All callers pass an explicit `checkpoint_id` derived from content hash when determinism is required.

---

## Finding 4 — Direct ledger writes in `validate_and_write_ledger.py`

**File:** `validate_and_write_ledger.py` lines 20–27  
**Pattern:** `open(LEDGER_FILE, "a")` with raw `f.write(json.dumps(record))` — bypasses `LedgerWriter`.  
**Problem:** Violates Rule 1 (only `agent_loop.py` / `LedgerWriter` may write ledger events). Writes lack `event_hash`, `rolling_hash`, `event_id`, and chain verification.  
**Fix:** `validate_and_write_ledger.py` updated to use `LedgerWriter.append()`. All ledger events must go through `LedgerWriter`.

---

## Finding 5 — Timestamp-based archive filenames in `message_ingestor.py`

**File:** `message_ingestor.py` line 47  
**Pattern:** `ts = datetime.now().strftime("%Y%m%d_%H%M%S")` used in filename  
**Problem:** Archive filenames are time-dependent; not used as identity, but can collide under parallel writes and prevents deterministic file listing.  
**Severity:** Low. Filenames are not used as message identity.  
**Fix:** Use `msg.get("message_id")` as the sole component of the archive filename (already present in the f-string but prefixed with a timestamp). Remove the timestamp prefix.

---

## Rules Confirmed Present

- `ledger_writer.py`: uses SHA256 hashes for `event_hash`, `rolling_hash`, `event_id` — deterministic.
- `state_serializer.py`: canonical JSON + SHA256 — deterministic.
- `graph_state.py`: `graph_hash()` via `state_serializer` — deterministic.
- `checkpoint_manager.py`: `state_hash()` for content verification — deterministic.
- No `import uuid`, `from uuid`, `random.`, `hash()` found in any `.py` file.

---

## Files Changed as Part of Audit Fixes

- `agent_message_schema.py` — deterministic ID generation via `generate_message_id()`
- `validate_and_write_ledger.py` — routes through `LedgerWriter`
- `message_ingestor.py` — removes timestamp from archive filename
- `message_bus.py` (new) — deterministic inbox/outbox, no timestamps in IDs
- `transcript.py` (new) — deterministic transcript IDs, no timestamps in IDs
- `deterministic_message_id.py` (new) — canonical SHA256 message IDs
