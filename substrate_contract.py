from substrate_errors import (
    SUBSTRATE_VERSION,
    E_DUPLICATE_MESSAGE_ID,
    E_MISSING_PARENT,
    E_PREVIOUS_HASH_MISMATCH,
    E_INVALID_JSON,
    E_MISSING_FINAL_NEWLINE,
)
from transcript_ledger import append_transcript_event as _append, verify_mixed_ledger as _verify
from transcript_validator import TranscriptValidationError

__all__ = [
    "SUBSTRATE_VERSION",
    "substrate_append_transcript_event",
    "substrate_verify_ledger",
]


def _classify_append_error(msg: str):
    if msg.startswith("duplicate message_id"):
        return E_DUPLICATE_MESSAGE_ID
    if msg.startswith("parent_message_id not in ledger"):
        return E_MISSING_PARENT
    return None


def _classify_verify_failure(msg: str):
    if "previous_hash mismatch" in msg:
        return E_PREVIOUS_HASH_MISMATCH
    if "invalid JSON" in msg:
        return E_INVALID_JSON
    if "missing final newline" in msg:
        return E_MISSING_FINAL_NEWLINE
    return None


def substrate_append_transcript_event(event: dict, path) -> dict:
    """
    Wraps append_transcript_event. Attaches .code to TranscriptValidationError when
    the error maps to a known substrate error constant. Message text is unchanged.
    """
    try:
        return _append(event, path)
    except TranscriptValidationError as e:
        code = _classify_append_error(str(e))
        if code is not None:
            e.code = code
        raise


def substrate_verify_ledger(path) -> dict:
    """
    Wraps verify_mixed_ledger. Adds error_codes list to result; all existing keys and
    failure message strings are preserved unchanged.
    """
    result = _verify(path)
    codes = []
    for failure in result.get("failures", []):
        code = _classify_verify_failure(failure)
        if code is not None:
            codes.append(code)
    return {**result, "error_codes": codes}
