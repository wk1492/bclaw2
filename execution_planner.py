def plan_execution(candidates):
    ready = []
    blocked = []

    for c in candidates:
        # Preserve FULL candidate object
        if c.get("status") == "proposed":
            ready.append(c)
        else:
            blocked.append(c)

    return {
        "ready": ready,
        "blocked": blocked,
    }
