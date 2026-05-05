import json
from collections import Counter
from pathlib import Path

LEDGER_FILE = Path("idea_ledger.jsonl")

def load_entries():
    if not LEDGER_FILE.exists():
        return []
    entries = []
    for line in LEDGER_FILE.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({"type": "malformed", "raw": line})
    return entries

def summarize_ledger():
    entries = load_entries()
    types = Counter(e.get("type", "unknown") for e in entries)
    validation_total = 0
    validation_pass = 0
    scores = []
    failures = Counter()

    for e in entries:
        for r in e.get("results", []):
            validation_total += 1
            if r.get("valid") is True:
                validation_pass += 1
            else:
                failures[r.get("error", "unknown_failure")] += 1
            if isinstance(r.get("score"), int):
                scores.append(r["score"])

    pass_rate = (validation_pass / validation_total) if validation_total else 0
    avg_score = (sum(scores) / len(scores)) if scores else 0

    return {
        "total_entries": len(entries),
        "entry_types": dict(types),
        "validation_total": validation_total,
        "validation_pass": validation_pass,
        "pass_rate": round(pass_rate, 3),
        "average_score": round(avg_score, 2),
        "top_failures": dict(failures.most_common(5)),
    }

if __name__ == "__main__":
    print(json.dumps(summarize_ledger(), indent=2))
