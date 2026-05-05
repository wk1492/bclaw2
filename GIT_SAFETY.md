## Safety Rule Added (Git Scope)

Before ANY git operation, ALWAYS verify repo root:

    git rev-parse --show-toplevel

Reason:
Prevents accidental operations on parent directories (e.g. /Users/bill) which can expose entire system files.

This rule is now REQUIRED for all agent and human workflows.
