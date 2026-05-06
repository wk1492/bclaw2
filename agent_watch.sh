#!/bin/sh
set -e

if [ "$#" -lt 1 ]; then
  echo "ALERT: no file supplied to agent_watch"
  exit 1
fi

TARGET="$1"

if [ ! -f "$TARGET" ]; then
  echo "ALERT: file not found: $TARGET"
  exit 1
fi

# Run code guard
python3 agent_code_guard.py "$TARGET"

echo "PASS: agent_watch cleared $TARGET"
