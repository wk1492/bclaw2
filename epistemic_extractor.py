"""
Deterministic structured-block extractor — BCLAW3 Phase 2A.

Reads transcript event content, extracts fenced bclaw blocks,
validates structure, and emits a deterministic artifact.

Never writes to ledger, FCM, or epistemic graph.
No model calls. No repair heuristics. No cross-message merging.
"""
import hashlib
import json
import re

EXTRACTOR_VERSION = 1

_BLOCK_PATTERN = re.compile(r"```bclaw\s*\n(.*?)```", re.DOTALL)


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_blocks(content: str) -> list:
    """Extract all bclaw-fenced blocks from free-text content.

    Returns list of parsed dicts. Malformed JSON or non-dict JSON
    produces an error entry: {"_error": "<msg>", "_raw": "<raw>"}.
    Free prose is silently ignored. Never raises.
    """
    results = []
    for match in _BLOCK_PATTERN.finditer(content):
        raw = match.group(1).strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            results.append({"_error": str(exc), "_raw": raw})
            continue
        if not isinstance(parsed, dict):
            results.append({"_error": "block must be a JSON object", "_raw": raw})
            continue
        results.append(parsed)
    return results


def validate_block(block: dict) -> dict:
    """Validate a single extracted block against the required-field contract.

    Returns {"ok": True, "block": block} or {"ok": False, "error": "...", "block": block}.
    """
    if "_error" in block:
        return {"ok": False, "error": block["_error"], "block": block}
    if "type" not in block:
        return {"ok": False, "error": "missing required field: type", "block": block}
    if not isinstance(block["type"], str) or not block["type"]:
        return {"ok": False, "error": "field 'type' must be a non-empty string", "block": block}
    if "payload" not in block:
        return {"ok": False, "error": "missing required field: payload", "block": block}
    if not isinstance(block["payload"], dict):
        return {"ok": False, "error": "field 'payload' must be a dict", "block": block}
    return {"ok": True, "block": block}


def extract_from_event(event: dict) -> dict:
    """Extract and validate all blocks from a single transcript event.

    Missing or non-string content yields empty blocks (not an error).
    Returns {"message_id": str, "blocks": list, "validated": list, "ok": bool}.
    """
    message_id = event.get("message_id", "")
    content = event.get("content", "")
    if not isinstance(content, str):
        content = ""

    blocks = extract_blocks(content)
    validated = [validate_block(b) for b in blocks]
    ok = all(v["ok"] for v in validated) if validated else True

    return {
        "message_id": message_id,
        "blocks": blocks,
        "validated": validated,
        "ok": ok,
    }


def extract_from_transcript(events: list) -> dict:
    """Process all transcript events and produce a deterministic extraction artifact.

    artifact_id is sha256 of canonical JSON of the artifact body.
    Empty event list and zero-block results are valid outputs.
    Never raises.
    """
    results = [extract_from_event(e) for e in events]
    block_count = sum(len(r["blocks"]) for r in results)
    error_count = sum(
        1
        for r in results
        for v in r["validated"]
        if not v["ok"]
    )

    artifact_body = {
        "block_count": block_count,
        "error_count": error_count,
        "results": results,
        "version": EXTRACTOR_VERSION,
    }
    artifact_id = _sha256(_canonical(artifact_body))

    return {
        "artifact_id": artifact_id,
        "block_count": block_count,
        "error_count": error_count,
        "results": results,
        "version": EXTRACTOR_VERSION,
    }
