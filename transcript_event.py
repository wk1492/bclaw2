import hashlib
import json

REQUIRED_FIELDS = {
    "event_type",
    "message_id",
    "run_id",
    "sender",
    "recipient",
    "role",
    "content",
    "references",
    "created_at",
    "metadata",
}

VALID_ROLES = {"proposal", "critique", "reply", "arbiter", "system"}
VALID_EVENT_TYPES = {"transcript.message"}


def canonical_json(event: dict) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def message_id_hash(event: dict) -> str:
    payload = {k: v for k, v in event.items() if k != "message_id"}
    return "tmsg_" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()[:24]


def make_transcript_event(
    run_id: str,
    sender: str,
    recipient: str,
    role: str,
    content: str,
    created_at: str,
    references: list = None,
    parent_message_id: str = None,
    metadata: dict = None,
) -> dict:
    event = {
        "event_type": "transcript.message",
        "run_id": run_id,
        "sender": sender,
        "recipient": recipient,
        "role": role,
        "content": content,
        "created_at": created_at,
        "references": references if references is not None else [],
        "parent_message_id": parent_message_id,
        "metadata": metadata if metadata is not None else {},
    }
    event["message_id"] = message_id_hash(event)
    return event
