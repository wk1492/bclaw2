def propose_execution(plan):
    ready = plan.get("ready", [])
    if not ready:
        return {
            "ready": False,
            "reason": "no ready candidates",
        }

    # lowest number = highest priority
    top = sorted(ready, key=lambda x: x.get("priority", 999))[0]

    return {
        "ready": True,
        "candidate_id": top.get("id"),
        "task_id": top.get("task_id"),
        "action": top.get("proposed_action"),
    }
