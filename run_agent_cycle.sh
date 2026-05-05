#!/bin/sh
set -e

echo "Running agent cycle..."

if [ ! -f agent_candidates.json ]; then
  echo "ERROR: agent_candidates.json not found"
  exit 1
fi

echo "Validating and storing candidates..."
python3 bridge_candidates_to_ledger.py agent_candidates.json

echo "Current IdeaLedger count:"
python3 - <<'PY'
from idea_ledger_v1.idea_ledger import IdeaLedger
ledger = IdeaLedger("test_ledger.jsonl")
print(len(ledger.list_all()))
PY

echo "Done."
