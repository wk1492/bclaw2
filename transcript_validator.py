from transcript_event import REQUIRED_FIELDS, VALID_ROLES, VALID_EVENT_TYPES


class TranscriptValidationError(ValueError):
    pass


def validate_transcript_event(event: dict) -> dict:
    if not isinstance(event, dict):
        raise TranscriptValidationError("event must be a dict")

    missing = REQUIRED_FIELDS - set(event)
    if missing:
        raise TranscriptValidationError(f"missing required fields: {sorted(missing)}")

    if event["event_type"] not in VALID_EVENT_TYPES:
        raise TranscriptValidationError(
            f"invalid event_type: {event['event_type']!r}; must be one of {sorted(VALID_EVENT_TYPES)}"
        )

    if not isinstance(event["message_id"], str) or not event["message_id"]:
        raise TranscriptValidationError("message_id must be a non-empty string")

    if not isinstance(event["run_id"], str) or not event["run_id"]:
        raise TranscriptValidationError("run_id must be a non-empty string")

    if not isinstance(event["sender"], str) or not event["sender"]:
        raise TranscriptValidationError("sender must be a non-empty string")

    if not isinstance(event["recipient"], str) or not event["recipient"]:
        raise TranscriptValidationError("recipient must be a non-empty string")

    if event["role"] not in VALID_ROLES:
        raise TranscriptValidationError(
            f"invalid role: {event['role']!r}; must be one of {sorted(VALID_ROLES)}"
        )

    if not isinstance(event["content"], str):
        raise TranscriptValidationError("content must be a string")

    if not isinstance(event["references"], list):
        raise TranscriptValidationError("references must be a list")

    if not isinstance(event["created_at"], str) or not event["created_at"]:
        raise TranscriptValidationError("created_at must be a non-empty string")

    if not isinstance(event["metadata"], dict):
        raise TranscriptValidationError("metadata must be a dict")

    return event


def reconstruct_thread(events: list) -> list:
    """Return events sorted by parent/child ordering, then message_id (canonical)."""
    roots = [e for e in events if e.get("parent_message_id") is None]
    children: dict = {}
    for e in events:
        pid = e.get("parent_message_id")
        if pid is not None:
            children.setdefault(pid, []).append(e)

    result = []

    def walk(node):
        result.append(node)
        for child in sorted(children.get(node["message_id"], []), key=lambda x: x["message_id"]):
            walk(child)

    for root in sorted(roots, key=lambda x: x["message_id"]):
        walk(root)

    return result
