def propose_execution(plan):
    ready = plan.get("ready", [])
    if ready:
        c = ready[0]
        return {
            "ready": True,
            "candidate_id": c.get("candidate_id"),
            "task_id": c.get("task_id"),
            "action": c.get("action"),
        }
    return {"ready": False}
