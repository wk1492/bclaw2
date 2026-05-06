def execute_proposal(proposal):
    if not proposal.get("ready"):
        return {
            "executed": False,
            "reason": proposal.get("reason", "not ready"),
        }

    return {
        "executed": True,
        "candidate_id": proposal.get("candidate_id"),
        "task_id": proposal.get("task_id"),
        "status": "simulated_execution",
    }
