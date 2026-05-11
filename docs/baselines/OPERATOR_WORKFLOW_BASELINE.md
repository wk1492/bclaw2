# Operator Workflow Baseline

Current HEAD: 3b6ef5f
Tests: 161 passed, 0 failed

## Interaction rules

- `1` means "continue the active already-scoped task" only if a task is actively in progress. If no task is active, `1` is not a task signal — do not act on it.
- After completing any task: report HEAD, test count, files changed, and whether pushed.
- Do not ask for confirmations except for destructive, ambiguous, or permission-sensitive actions.
- For docs/artifacts ignored by `.gitignore`, use `git add -f` when the user has explicitly requested baseline files.
- Prefer `uv tool run pytest -q` for this repo (system `python3` resolves to 3.14 without pytest).
- Do not rerun completed tasks. Verify current HEAD and git status instead.
- Never run tests or commands from `~`. Always `cd ~/Downloads/bclaw2` first.

## Repo state at this baseline

| Item | Value |
|---|---|
| HEAD | `3b6ef5f` |
| Tests | 161 passed, 0 failed |
| Test runner | `uv tool run pytest -q` |
| Push target | `origin/main` |
| Ignored dirs | `artifacts/`, `docs/` — force-add with `git add -f` |
