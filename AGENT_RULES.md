# BCLAW2 Agent Rules

## Permitted Actions

- Implement only the explicit approved task as relayed by the human.
- Run the full test suite after every change.
- Identify impossibility or contradiction in a task and report it.
- Choose the safest verifiable test if the requested test is impossible with current system state.

## Required Behavior

- **Every agentic step MUST call `assert_task_scope(action, description)` before making any changes.** Skipping this step is a protocol violation.
- Stop after completing one task and return the BCLAW2 STATUS block.
- Do not choose the next feature, expand scope, or continue beyond the directed step.
- Do not add tests unless new behavior or a new contract rule is introduced.
- Do not modify code behavior without an explicit directed task.

## Hard Limits

- No autonomous feature selection.
- No speculative implementation.
- No self-modification or recursive expansion.
- No action beyond the single directed step without human relay approval.

## Mechanical Enforcement

`guard.py` provides `check_task_scope(action, task_description)` and `assert_task_scope(action, task_description)`.

Any agentic execution step should call `assert_task_scope` before proceeding. This raises `RuntimeError` if the action is not in `ALLOWED_ACTIONS` or if the task description contains a forbidden pattern.

Allowed actions: `implement_directed_task`, `run_tests`, `report_impossibility`, `restore_missing_test_execution`.

Forbidden patterns (auto-detected in task description): choose next feature, expand scope, self modify, autonomous recursion, add test without new behavior.
