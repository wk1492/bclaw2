from datetime import UTC, datetime
import json

def generate_new_candidates(count=3):
    base_date = datetime.now(UTC).strftime("%Y%m%d")
    templates = [
        {
            "task_id": "ledger_analytics",
            "proposed_action": "Create ledger_analytics.py that produces summary reports from idea_ledger.jsonl including pass rate, average score, and failure patterns.",
            "rationale": "Turns raw ledger data into actionable insights for system improvement.",
            "evidence": "idea_ledger.jsonl already contains validation results, timestamps, and quality scores.",
            "risk_notes": "Purely read-only analysis. Very low risk.",
            "priority": 2,
            "estimated_impact": "medium"
        },
        {
            "task_id": "loop_enhancement",
            "proposed_action": "Add candidate archiving logic so completed ideas are moved out of the active queue.",
            "rationale": "Prevents the active list from growing indefinitely and keeps focus on new work.",
            "evidence": "Current design has no archiving step after implementation.",
            "risk_notes": "Low risk if done as a separate status transition.",
            "priority": 2,
            "estimated_impact": "medium"
        }
    ]

    candidates = []
    for i, item in enumerate(templates[:count], 1):
        candidates.append({
            "id": f"candidate-{base_date}-{i:03d}",
            "source_model": "bclaw",
            "task_id": item["task_id"],
            "proposed_action": item["proposed_action"],
            "rationale": item["rationale"],
            "evidence": item["evidence"],
            "risk_notes": item["risk_notes"],
            "status": "proposed",
            "priority": item["priority"],
            "estimated_impact": item["estimated_impact"],
            "dependencies": [],
            "metadata": {}
        })
    return candidates

if __name__ == "__main__":
    print(json.dumps(generate_new_candidates(), indent=2))
