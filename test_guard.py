# BCLAW2 Guard Tests
from guard import check_task_scope, assert_task_scope

def test_guard_allows_valid_action():
    result = check_task_scope("run_tests", "run the full test suite")
    assert result["allowed"] is True

def test_guard_blocks_invalid_action():
    result = check_task_scope("do_something_else", "implement a feature")
    assert result["allowed"] is False

def test_guard_blocks_forbidden_pattern():
    result = check_task_scope("implement_directed_task", "choose next feature to build")
    assert result["allowed"] is False

def test_guard_assert_raises_on_forbidden():
    try:
        assert_task_scope("implement_directed_task", "expand scope of the system")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass

def test_guard_denied_reason_is_clear():
    result = check_task_scope("do_something_else", "implement a feature")
    assert result["allowed"] is False
    assert "do_something_else" in result["reason"]
    assert len(result["reason"]) > 10

if __name__ == "__main__":
    test_guard_allows_valid_action()
    print("PASS: guard allows valid action")
    test_guard_blocks_invalid_action()
    print("PASS: guard blocks invalid action")
    test_guard_blocks_forbidden_pattern()
    print("PASS: guard blocks forbidden pattern in task description")
    test_guard_assert_raises_on_forbidden()
    print("PASS: guard assert_task_scope raises RuntimeError on forbidden task")
    test_guard_denied_reason_is_clear()
    print("PASS: guard denied action includes clear reason string")
