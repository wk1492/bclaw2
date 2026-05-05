from execution_planner import plan_execution

def test_blocks_unmet_dependency():
    candidates = [
        {
            "id": "candidate-a",
            "status": "proposed",
            "priority": 2,
            "task_id": "a",
            "proposed_action": "Do A",
            "dependencies": []
        },
        {
            "id": "candidate-b",
            "status": "proposed",
            "priority": 1,
            "task_id": "b",
            "proposed_action": "Do B",
            "dependencies": ["candidate-a"]
        }
    ]
    plan = plan_execution(candidates)
    assert [x["id"] for x in plan["ready"]] == ["candidate-a"]
    assert [x["id"] for x in plan["blocked"]] == ["candidate-b"]

def test_allows_completed_dependency():
    candidates = [
        {
            "id": "candidate-a",
            "status": "implemented",
            "priority": 2,
            "task_id": "a",
            "proposed_action": "Do A",
            "dependencies": []
        },
        {
            "id": "candidate-b",
            "status": "proposed",
            "priority": 1,
            "task_id": "b",
            "proposed_action": "Do B",
            "dependencies": ["candidate-a"]
        }
    ]
    plan = plan_execution(candidates)
    assert [x["id"] for x in plan["ready"]] == ["candidate-b"]
    assert plan["blocked"] == []

if __name__ == "__main__":
    test_blocks_unmet_dependency()
    test_allows_completed_dependency()
    print("PASS: execution planner respects dependencies")
