#!/bin/sh
set -e

# Git safety
./git_preflight.sh

# Agent safety
./agent_watch.sh \"$@\"

# If both pass, continue
exec \"$@\"
