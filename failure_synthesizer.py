from pathlib import Path
import json

PATTERNS = [
    {
        "id": "git_state_normalization",
        "symptoms": ["repository not found", "unable to add remote", "no configured push destination"],
        "proposal": "Use git_safe_push.sh which normalizes remote and root checks",
        "artifact": "git_safe_push.sh",
    },
]


def synthesize(text):
    text_l = text.lower()
    matches = []
    for pattern in PATTERNS:
        hit = [s for s in pattern["symptoms"] if s in text_l]
        if hit:
            matches.append({
                "pattern_id": pattern["id"],
                "matched_symptoms": hit,
                "proposal": pattern["proposal"],
                "artifact": pattern["artifact"],
            })
    return matches


if __name__ == "__main__":
    source = Path("failure_notes.txt")
    if not source.exists():
        source.write_text("repository not found\nunable to add remote\nno configured push destination\n")
    results = synthesize(source.read_text())
    print(json.dumps(results, indent=2))
