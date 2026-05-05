from pathlib import Path
from agent_code_guard import check_text


def test_blocks_rm_rf():
    p = Path("tmp_bad_agent_change.py")
    p.write_text("rm -rf /")
    problems = check_text(str(p))
    p.unlink()
    assert problems


def test_allows_safe_python():
    p = Path("tmp_good_agent_change.py")
    p.write_text("print(\"safe\")")
    problems = check_text(str(p))
    p.unlink()
    assert problems == []


if __name__ == "__main__":
    test_blocks_rm_rf()
    test_allows_safe_python()
    print("PASS: agent code guard blocks dangerous code")
