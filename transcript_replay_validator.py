from transcript import get_transcript_hash

REQUIRED_TRANSCRIPT_FIELDS = {"transcript_id", "candidate_id", "turns", "transcript_hash"}
REQUIRED_TURN_FIELDS = {"message_id", "sender", "recipient", "role", "turn_number", "payload"}


def validate_transcript_schema(transcript: dict) -> list:
    errors = []
    for field in REQUIRED_TRANSCRIPT_FIELDS:
        if field not in transcript:
            errors.append(f"Missing transcript field: {field!r}")

    for i, turn in enumerate(transcript.get("turns", [])):
        missing = REQUIRED_TURN_FIELDS - set(turn.keys())
        if missing:
            errors.append(f"Turn {i} missing fields: {missing}")

    return errors


def verify_transcript_hash(transcript: dict) -> dict:
    errors = validate_transcript_schema(transcript)
    if errors:
        return {"ok": False, "errors": errors}

    stored = transcript["transcript_hash"]
    computed = get_transcript_hash(transcript)

    if stored != computed:
        return {
            "ok": False,
            "errors": [f"transcript_hash mismatch: stored={stored[:16]}… computed={computed[:16]}…"],
        }

    return {"ok": True, "errors": [], "transcript_hash": computed}


def compare_transcripts(original: dict, replayed: dict) -> dict:
    orig = verify_transcript_hash(original)
    if not orig["ok"]:
        return {"ok": False, "errors": [f"original: {e}" for e in orig["errors"]]}

    repl = verify_transcript_hash(replayed)
    if not repl["ok"]:
        return {"ok": False, "errors": [f"replayed: {e}" for e in repl["errors"]]}

    if original["transcript_hash"] != replayed["transcript_hash"]:
        return {
            "ok": False,
            "errors": [
                f"hash mismatch: original={original['transcript_hash'][:16]}… "
                f"replayed={replayed['transcript_hash'][:16]}…"
            ],
        }

    return {"ok": True, "errors": [], "transcript_hash": original["transcript_hash"]}
