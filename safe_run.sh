#!/bin/sh
set -e

./git_preflight.sh

if [ "$#" -lt 1 ]; then
    echo "ALERT: no command supplied to safe_run"
    exit 1
fi

case "$1" in
    python3|python)
        if [ "$#" -lt 2 ]; then
            echo "ALERT: no python file supplied"
            exit 1
        fi
        TARGET="$2"
        if [ ! -f "$TARGET" ]; then
            echo "ALERT: file does not exist: $TARGET"
            exit 1
        fi
        ./agent_watch.sh "$TARGET"
        ;;
    sh|bash)
        if [ "$#" -lt 2 ]; then
            echo "ALERT: no shell file supplied"
            exit 1
        fi
        TARGET="$2"
        ./agent_watch.sh "$TARGET"
        ;;
    *)
        echo "ALERT: unsupported command: $1"
        exit 1
        ;;
esac

exec "$@"
