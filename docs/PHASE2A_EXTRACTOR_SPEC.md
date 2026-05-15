# Phase 2A: Deterministic Structured-Block Extractor Spec

**Version:** 1  
**Status:** Design — implementation in `epistemic_extractor.py`

---

## 1. Purpose

Extract structured computation blocks from free-text transcript content.
The extractor reads, never writes. It never mutates the ledger, FCM, or epistemic graph.
Free prose is ignored. Only explicitly delimited blocks produce artifacts.

---

## 2. Block Format

Agents embed structured blocks using fenced code blocks with the `bclaw` language tag:

```
```bclaw
{"type": "<block_type>", "payload": {...}}
```
```

The extractor keys on this delimiter only. All other content is free prose and is silently ignored.

### Required block fields

| Field | Type | Constraint |
|---|---|---|
| `type` | str | non-empty |
| `payload` | dict | any dict |

---

## 3. API Contract

### `extract_blocks(content: str) -> list[dict]`

Scans `content` for `bclaw`-fenced blocks. Returns a list of parsed dicts.
- Malformed JSON produces an error entry: `{"_error": "<msg>", "_raw": "<raw text>"}`
- Non-dict JSON (array, scalar) produces an error entry
- Empty list is a valid result

### `validate_block(block: dict) -> dict`

Validates a single block dict against the required-field contract.
- Valid: `{"ok": True, "block": block}`
- Invalid: `{"ok": False, "error": "<reason>", "block": block}`
- Error entries (containing `_error`) produce `ok: False`

### `extract_from_event(event: dict) -> dict`

Extracts and validates all blocks from `event["content"]`.
- Missing or non-string `content` yields empty blocks (not an error)
- Returns: `{"message_id": str, "blocks": list, "validated": list, "ok": bool}`
- `ok` is True iff all validated entries pass (or there are none)

### `extract_from_transcript(events: list) -> dict`

Processes all events; produces a deterministic extraction artifact.
- Returns:
  ```json
  {
    "artifact_id": "<sha256>",
    "version": 1,
    "results": [...],
    "block_count": N,
    "error_count": N
  }
  ```
- `artifact_id` is `sha256(canonical_json({"results": ..., "block_count": ..., "error_count": ..., "version": 1}))`
- Empty event list is valid: `block_count=0`, `error_count=0`

---

## 4. Determinism Contract

- Same input bytes → same `artifact_id` across all runs, processes, seeds
- No timestamps, no random, no OS state
- Canonical JSON: `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`
- `EXTRACTOR_VERSION = 1`

---

## 5. Failure Modes

| Code | Meaning | Behavior |
|---|---|---|
| `EXTRACTION_EMPTY` | No blocks found | Valid result, `block_count=0` |
| `EXTRACTION_AMBIGUOUS` | Block found, JSON parse fails | Error entry with `_error`, included in `error_count` |
| `SCHEMA_INVALID` | Block parsed but fails field contract | `ok: False` in validated entry, included in `error_count` |

Failed extraction is always valid output. The extractor never raises.

---

## 6. Hard Boundaries

- No ledger writes
- No FCM mutation
- No semantic validation (type values are not interpreted)
- No free-prose inference
- No cross-message merging
- No model calls
- No repair heuristics

---

## 7. Required Tests (14)

1. `test_extract_blocks_empty_string` — empty string → []
2. `test_extract_blocks_prose_only` — prose without fences → []
3. `test_extract_blocks_single_valid_block` — one block → [parsed dict]
4. `test_extract_blocks_multiple_blocks` — two blocks → [dict1, dict2]
5. `test_extract_blocks_malformed_json_produces_error_entry` — bad JSON → `_error` key present
6. `test_validate_block_valid_passes` — required fields present → ok=True
7. `test_validate_block_missing_type_fails` — no `type` → ok=False
8. `test_validate_block_missing_payload_fails` — no `payload` → ok=False
9. `test_validate_block_payload_not_dict_fails` — `payload` is list → ok=False
10. `test_extract_from_event_no_blocks_ok` — event with prose → ok=True, blocks=[]
11. `test_extract_from_event_with_valid_block` — event with one block → ok=True, one validated entry
12. `test_extract_from_transcript_empty_events` — [] → artifact_id present, block_count=0
13. `test_extract_from_transcript_two_events` — two events, one block each → block_count=2
14. `test_artifact_id_is_deterministic` — same input run twice → identical artifact_id
