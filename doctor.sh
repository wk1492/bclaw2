#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

STRICT=false
for arg in "$@"; do
    [ "$arg" = "--strict" ] && STRICT=true
done

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

# Dry-run contract check (case-insensitive)
if grep -qiE "ollama|subprocess|requests|openai|api_key|http" model_runner.py; then
    echo "❌ doctor: runner contract violation (non-dry-run elements detected)"
    exit 1
fi

echo "✅ doctor: deterministic model runner abstraction passes"

if $STRICT; then
    echo "→ Running strict environment integrity checks..."

    # Repo root identity
    EXPECTED_ROOT="$HOME/Downloads/bclaw2"
    ACTUAL_ROOT="$(pwd -P)"
    EXPECTED_REAL="$(cd "$EXPECTED_ROOT" 2>/dev/null && pwd -P || echo "MISSING")"
    if [ "$ACTUAL_ROOT" != "$EXPECTED_REAL" ]; then
        echo "❌ doctor --strict: wrong repo root"
        echo "   expected: $EXPECTED_REAL"
        echo "   actual:   $ACTUAL_ROOT"
        echo "   → cd ~/Downloads/bclaw2 and retry"
        exit 1
    fi

    # Clean worktree (no staged or unstaged changes to tracked files)
    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo "❌ doctor --strict: git worktree is dirty (uncommitted changes present)"
        exit 1
    fi

    # Branch must be main
    BRANCH="$(git branch --show-current)"
    if [ "$BRANCH" != "main" ]; then
        echo "❌ doctor --strict: not on main branch (current: $BRANCH)"
        exit 1
    fi

    # Required substrate files
    for f in transcript_event.py transcript_ledger.py transcript_topology.py \
              model_runner.py SUBSTRATE_CONTRACT.md; do
        if [ ! -f "$f" ]; then
            echo "❌ doctor --strict: required substrate file missing: $f"
            exit 1
        fi
    done

    # Runner test must pass standalone
    if ! uv tool run pytest test_model_runner.py -q > /dev/null; then
        echo "❌ doctor --strict: test_model_runner.py failed"
        exit 1
    fi

    # Runner dry-run contract (redundant but explicit in strict mode)
    if grep -qiE "ollama|subprocess|requests|openai|api_key|http" model_runner.py; then
        echo "❌ doctor --strict: runner contract violation"
        exit 1
    fi

    echo "✅ doctor --strict: strict environment integrity passed"
fi

echo "=== BCLAW2 DOCTOR PASS ==="
