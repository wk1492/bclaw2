import json
from pathlib import Path

MEMORY_DIR = Path("transcript_memory")
INDEX_FILE = MEMORY_DIR / "index.json"
MAX_SEARCH_RESULTS = 10


def _load_index() -> list:
    if not INDEX_FILE.exists():
        return []
    return json.loads(INDEX_FILE.read_text())


def _save_index(entries: list) -> None:
    MEMORY_DIR.mkdir(exist_ok=True)
    INDEX_FILE.write_text(
        json.dumps(
            sorted(entries, key=lambda e: e["transcript_id"]),
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def archive_transcript(transcript: dict) -> str:
    MEMORY_DIR.mkdir(exist_ok=True)
    tid = transcript["transcript_id"]
    path = MEMORY_DIR / f"{tid}.json"
    path.write_text(json.dumps(transcript, sort_keys=True, separators=(",", ":")))

    index = _load_index()
    existing_ids = {e["transcript_id"] for e in index}
    if tid not in existing_ids:
        index.append({
            "transcript_id": tid,
            "candidate_id": transcript.get("candidate_id"),
            "transcript_hash": transcript.get("transcript_hash"),
            "turn_count": transcript.get("turn_count", len(transcript.get("turns", []))),
        })
        _save_index(index)

    return tid


def search_transcripts(candidate_id: str = None, transcript_hash: str = None) -> list:
    index = _load_index()
    results = []
    for entry in index:
        if candidate_id is not None and entry.get("candidate_id") != candidate_id:
            continue
        if transcript_hash is not None and entry.get("transcript_hash") != transcript_hash:
            continue
        results.append(entry)
        if len(results) >= MAX_SEARCH_RESULTS:
            break
    return results


def load_transcript(transcript_id: str) -> dict:
    path = MEMORY_DIR / f"{transcript_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_id!r}")
    return json.loads(path.read_text())
