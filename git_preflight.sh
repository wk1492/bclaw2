#!/bin/sh
set -e
EXPECTED_ROOT="$HOME/Downloads/bclaw2"
ACTUAL_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ "$ACTUAL_ROOT" != "$EXPECTED_ROOT" ]; then
  echo "ALERT: wrong git root: $ACTUAL_ROOT"
  echo "EXPECTED: $EXPECTED_ROOT"
  exit 1
fi
if ! git remote get-url origin >/dev/null 2>&1; then
  echo "ALERT: no git remote configured"
  exit 1
fi
echo "PASS: git preflight ok"
