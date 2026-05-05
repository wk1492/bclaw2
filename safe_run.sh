#!/bin/sh
set -e

if [ "$#" -lt 1 ]; then
  echo "ALERT: no command supplied to safe_run"
  exit 1
fi

./git_preflight.sh

case "$1" in
  python3|python)
    if [ "$#" -lt 2 ]; then
      echo "ALERT: no python file supplied"
      exit 1
    fi
    ./agent_watch.sh "$2"
    ;;
  sh|bash)
    if [ "$#" -lt 2 ]; then
      echo "ALERT: no shell file supplied"
      exit 1
    fi
    ./agent_watch.sh "$2"
    ;;
  *)
    echo "ALERT: unsupported command: $1"
    exit 1
    ;;
esac

exec "$@"
