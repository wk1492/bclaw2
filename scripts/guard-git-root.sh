#!/usr/bin/env bash
# scripts/guard-git-root.sh - Strict root enforcement for BCLAW2

set -euo pipefail

EXPECTED_ROOT="${HOME}/Downloads/bclaw2"
CURRENT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "NO_GIT")"

if [[ "$CURRENT_ROOT" == "NO_GIT" ]]; then
    echo "FATAL: Not inside a git repository" >&2
    exit 1
fi

REAL_EXPECTED="$(realpath -e "$EXPECTED_ROOT" 2>/dev/null || echo "$EXPECTED_ROOT")"
REAL_CURRENT="$(realpath -e "$CURRENT_ROOT" 2>/dev/null || echo "$CURRENT_ROOT")"

if [[ "$REAL_CURRENT" != "$REAL_EXPECTED" ]]; then
    echo "FATAL: Git root corruption detected!" >&2
    echo "   Expected: $EXPECTED_ROOT" >&2
    echo "   Actual:   $CURRENT_ROOT" >&2
    echo "   Real expected: $REAL_EXPECTED" >&2
    echo "   Real current:  $REAL_CURRENT" >&2
    echo "" >&2
    echo "Run from correct directory or fix with: cd ~/Downloads/bclaw2" >&2
    exit 1
fi

export BCLAW2_ROOT="$REAL_CURRENT"
cd "$BCLAW2_ROOT"

echo "PASS: git root verified: $BCLAW2_ROOT"
