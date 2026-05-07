#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== BCLAW2 FINAL RESET ==="

# Clean state
rm -f execution_ledger.jsonl

# Fresh valid candidate
python3 - <<'PY'
import json
from pathlib import Path

candidate = {
    "candidate_id": "test_underperformance_001",
    "id": "test_underperformance_001",
    "source_model": "manual",
    "task_id": "underperformance_v1",
    "action": "Run manual underperformance experiment under locked v1 contract",
    "proposed_action": "Run manual underperformance experiment under locked v1 contract",
    "rationale": "Test predict_observe_evaluate_log_only loop with deterministic ledger",
    "evidence": "underperformance_v1 contract committed",
    "risk_notes": "Synthetic test only",
    "status": "proposed"
}

Path("agent_candidates.json").write_text(json.dumps([candidate], indent=2) + "\n")
print("✅ Created valid underperformance candidate")
PY

echo "=== RUNNING AGENT LOOP ==="
python3 agent_loop.py

echo "=== SYSTEM VERIFICATION ==="
python3 verify_system.py

echo "=== FULL REPLAY VERIFICATION ==="
python3 replay_runner.py --verify

echo "=== BCLAW2 FINAL PUSH COMPLETE ==="
