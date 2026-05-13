#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "=== BCLAW2 DOCTOR ==="

# === Runner v1 Validation (deterministic contract) ===
echo "→ Validating model runner v1 abstraction..."
if [ ! -f "model_runner.py" ]; then
    echo "❌ doctor: model_runner.py missing"
    exit 1
fi
if [ ! -f "test_model_runner.py" ]; then
    echo "❌ doctor: test_model_runner.py missing"
    exit 1
fi

if ! uv tool run pytest test_model_runner.py -q > /dev/null; then
    echo "❌ doctor: test_model_runner.py failed"
    exit 1
fi

if ! uv tool run pytest -q > /dev/null; then
    echo "❌ doctor: full test suite failed"
    exit 1
fi

# Improved dry-run contract check (case-insensitive)
if grep -qiE "ollama|subprocess|requests|openai|api_key|http" model_runner.py; then
    echo "❌ doctor: runner contract violation (non-dry-run elements detected)"
    exit 1
fi

echo "✅ doctor: deterministic model runner abstraction passes"

echo "=== BCLAW2 DOCTOR PASS ==="
