def plan_execution(candidates):
    ready = []
    blocked = []

    implemented = {c["id"] for c in candidates if c.get("status") == "implemented"}

    for c in candidates:
        if c.get("status") != "proposed":
            continue
        if all(d in implemented for d in c.get("dependencies", [])):
            ready.append(c)
        else:
            blocked.append(c)

    return {
        "ready": ready,
        "blocked": blocked,
    }
