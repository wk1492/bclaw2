import json
from pathlib import Path

INBOX_DIR = Path("inbox")
OUTBOX_DIR = Path("outbox")

REQUIRED_MESSAGE_FIELDS = {"message_id", "candidate_id", "sender", "recipient", "role", "turn_number", "payload"}


def _validate(msg: dict) -> None:
    missing = REQUIRED_MESSAGE_FIELDS - set(msg.keys())
    if missing:
        raise ValueError(f"Message missing required fields: {missing}")
    if not str(msg["message_id"]).startswith("msg_"):
        raise ValueError(f"message_id must start with 'msg_': {msg['message_id']!r}")


def put_inbox(message: dict) -> Path:
    _validate(message)
    recipient = message["recipient"]
    msg_id = message["message_id"]
    dest = INBOX_DIR / recipient / f"{msg_id}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(message, sort_keys=True, separators=(",", ":")))
    return dest


def get_inbox(recipient: str) -> list:
    inbox = INBOX_DIR / recipient
    if not inbox.exists():
        return []
    messages = []
    for path in sorted(inbox.glob("*.json")):
        messages.append(json.loads(path.read_text()))
    return sorted(messages, key=lambda m: m.get("turn_number", 0))


def put_outbox(message: dict) -> Path:
    _validate(message)
    sender = message["sender"]
    msg_id = message["message_id"]
    dest = OUTBOX_DIR / sender / f"{msg_id}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(message, sort_keys=True, separators=(",", ":")))
    return dest


def get_outbox(sender: str) -> list:
    outbox = OUTBOX_DIR / sender
    if not outbox.exists():
        return []
    messages = []
    for path in sorted(outbox.glob("*.json")):
        messages.append(json.loads(path.read_text()))
    return sorted(messages, key=lambda m: m.get("turn_number", 0))


def clear_inbox(recipient: str) -> None:
    inbox = INBOX_DIR / recipient
    if inbox.exists():
        for path in inbox.glob("*.json"):
            path.unlink()


def clear_outbox(sender: str) -> None:
    outbox = OUTBOX_DIR / sender
    if outbox.exists():
        for path in outbox.glob("*.json"):
            path.unlink()
