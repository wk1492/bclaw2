# BCLAW2 Guard Layer - mechanical enforcement of AGENT_RULES.md constraints
# Import and call check_task_scope() at the start of any agentic execution step.

ALLOWED_ACTIONS = frozenset([
    "implement_directed_task",
    "run_tests",
    "report_impossibility",
    "restore_missing_test_execution",
])

FORBIDDEN_PATTERNS = [
    "choose_next_feature",
    "expand_scope",
    "self_modify",
    "autonomous_recursion",
    "add_test_without_new_behavior",
]

def check_task_scope(action: str, task_description: str) -> dict:
    """
    Call before executing any step. Returns {"allowed": True/False, "reason": str}.
    action     : one of ALLOWED_ACTIONS
    task_description : brief plain-text description of what will be done
    """
    if action not in ALLOWED_ACTIONS:
        return {
            "allowed": False,
            "reason": f"action '{action}' is not in ALLOWED_ACTIONS: {sorted(ALLOWED_ACTIONS)}"
        }
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.replace("_", " ") in task_description.lower():
            return {
                "allowed": False,
                "reason": f"task_description contains forbidden pattern: '{pattern}'"
            }
    return {"allowed": True, "reason": "task passes scope check"}

def assert_task_scope(action: str, task_description: str) -> None:
    """Raises RuntimeError if task fails scope check."""
    result = check_task_scope(action, task_description)
    if not result["allowed"]:
        raise RuntimeError(f"[GUARD] Task blocked: {result['reason']}")
