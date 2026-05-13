"""
Deterministic diff between two transcript event sets.

Pure functional — no side effects, no model calls, no randomness.
Output is content-addressed and byte-identical across runs.
"""
import hashlib
import json


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def diff_transcript_events(before: list, after: list) -> dict:
    """
    Compute a deterministic diff between two transcript event sets.

    Events are identified by message_id. Order within each set does not matter;
    the diff is purely set-based.

    Returns a JSON-safe dict:
        added         — events in after but not in before, sorted by message_id
        removed       — events in before but not in after, sorted by message_id
        unchanged     — events in both, sorted by message_id
        added_ids     — sorted list of added message_ids
        removed_ids   — sorted list of removed message_ids
        unchanged_ids — sorted list of unchanged message_ids
        diff_id       — "tdiff_" + sha256[:24] of canonical({added_ids, removed_ids, unchanged_ids})
    """
    before_by_id = {e["message_id"]: e for e in before}
    after_by_id = {e["message_id"]: e for e in after}

    before_ids = set(before_by_id)
    after_ids = set(after_by_id)

    added_ids = sorted(after_ids - before_ids)
    removed_ids = sorted(before_ids - after_ids)
    unchanged_ids = sorted(before_ids & after_ids)

    diff_payload = {
        "added_ids": added_ids,
        "removed_ids": removed_ids,
        "unchanged_ids": unchanged_ids,
    }
    diff_id = "tdiff_" + _sha256(_canonical(diff_payload))[:24]

    return {
        "added": [after_by_id[mid] for mid in added_ids],
        "removed": [before_by_id[mid] for mid in removed_ids],
        "unchanged": [before_by_id[mid] for mid in unchanged_ids],
        "added_ids": added_ids,
        "removed_ids": removed_ids,
        "unchanged_ids": unchanged_ids,
        "diff_id": diff_id,
    }
