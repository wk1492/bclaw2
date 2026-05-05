#!/bin/sh
set -e

EXPECTED_ROOT="$HOME/Downloads/bclaw2"
EXPECTED_REMOTE="https://github.com/wk1492/bclaw2.git"

ACTUAL_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ "$ACTUAL_ROOT" != "$EXPECTED_ROOT" ]; then
  echo "ALERT: wrong git root: $ACTUAL_ROOT"
  echo "EXPECTED: $EXPECTED_ROOT"
  exit 1
fi

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$EXPECTED_REMOTE"
else
  git remote add origin "$EXPECTED_REMOTE"
fi

echo "REMOTE: $(git remote get-url origin)"
git push -u origin main
