#!/usr/bin/env bash
set -euo pipefail

EXPECTED_COUNT=323
PYTEST="uv tool run pytest"

# Verify environment
if ! command -v uv >/dev/null 2>&1; then
    echo "FAIL: uv not found in PATH"
    exit 1
fi
if [ ! -f "transcript_ledger.py" ]; then
    echo "FAIL: must be run from bclaw2 project root"
    exit 1
fi

# Required test files
for f in test_transcript_hardening.py test_transcript_append_hardening.py test_crash_consistency_hardening.py; do
    if [ ! -f "$f" ]; then
        echo "FAIL: missing required file: $f"
        exit 1
    fi
done

# Stage 1: hardening suites first
echo "STAGE 1 hardening"
$PYTEST test_transcript_hardening.py test_transcript_append_hardening.py test_crash_consistency_hardening.py \
    -q --tb=short --no-header --color=no -p no:cacheprovider
echo "STAGE 1 ok"

# Stage 2: deterministic collected-test count (no execution, no text parsing)
echo "STAGE 2 count check"
ACTUAL=$($PYTEST --collect-only -q --no-header --color=no -p no:cacheprovider 2>&1 \
    | grep -c "::") || true
if [ -z "$ACTUAL" ] || [ "$ACTUAL" != "$EXPECTED_COUNT" ]; then
    echo "FAIL: expected $EXPECTED_COUNT tests, got ${ACTUAL:-unknown}"
    exit 1
fi
echo "STAGE 2 ok collected=$ACTUAL"

# Stage 3: full suite run
echo "STAGE 3 full suite"
$PYTEST -q --tb=short --no-header --color=no -p no:cacheprovider
echo "STAGE 3 ok"

echo "verify_substrate ok $ACTUAL"
