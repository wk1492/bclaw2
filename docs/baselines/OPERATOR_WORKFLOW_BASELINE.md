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
- **Run `./doctor.sh --strict` before any mutation, schema change, orchestration change, runner/transcript wiring, or FCM/graph work.**
- **If strict doctor fails repo identity, stop immediately and `cd ~/Downloads/bclaw2`.**

## Failure mode: coherent-output-on-wrong-lineage

**Definition:** Work produced from the wrong repository, branch, or architectural
lineage that is internally coherent but semantically irrelevant or contaminating
to the BCLAW2 substrate.

**Why it is dangerous:**
- Diffs may look valid and tests may pass — but in the wrong repo with a different schema.
- Commits may be coherent but address the wrong codebase entirely.
- Old schemas or orchestrators from prior projects can silently contaminate BCLAW2 data structures.
- The failure is invisible until a frozen baseline hash diverges or replay produces unexpected output.

**Required prevention:**
- Run `./doctor.sh --strict` before mutation work.
- Verify repo root is exactly `~/Downloads/bclaw2`.
- Verify branch is `main`.
- Verify required substrate files exist (see doctor.sh --strict).
- Stop immediately on identity failure. Do not continue. Re-run from the correct location.

**Workspace identity is a substrate precondition, not a convenience check.**

## Repo state at this baseline

| Item | Value |
|---|---|
| HEAD | `3b6ef5f` |
| Tests | 161 passed, 0 failed |
| Test runner | `uv tool run pytest -q` |
| Push target | `origin/main` |
| Ignored dirs | `artifacts/`, `docs/` — force-add with `git add -f` |
