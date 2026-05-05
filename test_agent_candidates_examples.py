# BCLAW2 Agent Candidate Examples Tests
from candidate_validator import validate_candidate
from agent_candidates_examples import (
    EXAMPLE_AGENT_CANDIDATE_VALID,
    EXAMPLE_AGENT_CANDIDATE_INVALID_MISSING_STATUS,
)

def test_agent_candidate_examples():
    # valid example passes
    validate_candidate(EXAMPLE_AGENT_CANDIDATE_VALID)
    # invalid example raises ValueError
    try:
        validate_candidate(EXAMPLE_AGENT_CANDIDATE_INVALID_MISSING_STATUS)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "status" in str(e)

def test_candidate_fixture_isolation():
    import ast, pathlib
    pipeline_modules = ["orchestrator.py", "fusion.py", "dynamics.py"]
    base = pathlib.Path(__file__).parent
    for module in pipeline_modules:
        source = (base / module).read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else ([node.module] if node.module else [])
                )
                for name in names:
                    assert "agent_candidates_examples" not in (name or ""), \
                        f"{module} must not import agent_candidates_examples"

if __name__ == "__main__":
    test_agent_candidate_examples()
    print("PASS: valid candidate passes, invalid candidate raises ValueError for missing status")
    test_candidate_fixture_isolation()
    print("PASS: agent_candidates_examples not imported by any pipeline module")
