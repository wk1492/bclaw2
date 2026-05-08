import hashlib
import json
from state_serializer import canonical_json

REQUIRED_TURN_FIELDS = {"message_id", "sender", "recipient", "role", "turn_number", "payload"}


def _transcript_content(candidate_id: str, turns: list) -> dict:
    return {
        "candidate_id": candidate_id,
        "turns": sorted(turns, key=lambda t: t["turn_number"]),
    }


def _hash(content: dict) -> str:
    return hashlib.sha256(canonical_json(content).encode("utf-8")).hexdigest()


def build_transcript(candidate_id: str, turns: list) -> dict:
    for i, turn in enumerate(turns):
        missing = REQUIRED_TURN_FIELDS - set(turn.keys())
        if missing:
            raise ValueError(f"Turn {i} missing required fields: {missing}")

    content = _transcript_content(candidate_id, turns)
    transcript_hash = _hash(content)

    return {
        "transcript_id": f"txn_{transcript_hash[:32]}",
        "candidate_id": candidate_id,
        "turns": content["turns"],
        "transcript_hash": transcript_hash,
        "turn_count": len(turns),
    }


def get_transcript_hash(transcript: dict) -> str:
    content = _transcript_content(transcript["candidate_id"], transcript["turns"])
    return _hash(content)
