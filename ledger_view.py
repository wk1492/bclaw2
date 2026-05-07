import argparse
import json
from pathlib import Path

LEDGER_FILE = Path("test_ledger.jsonl")

def load_ideas(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default=str(LEDGER_FILE))
    parser.add_argument("--last", type=int, default=5)
    parser.add_argument("--source")
    parser.add_argument("--tag")
    args = parser.parse_args()

    ideas = load_ideas(Path(args.file))

    if args.source:
        ideas = [i for i in ideas if i.get("source") == args.source]

    if args.tag:
        ideas = [i for i in ideas if args.tag in i.get("tags", [])]

    print(f"idea_count={len(ideas)}")

    for idea in ideas[-args.last:]:
        print(json.dumps({
            "id": idea.get("id"),
            "source": idea.get("source"),
            "status": idea.get("status"),
            "tags": idea.get("tags", []),
            "raw_text": idea.get("raw_text"),
        }, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
