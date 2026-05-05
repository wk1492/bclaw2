# BCLAW2 Phase 2 - Fusion (configurable strategy, conflict detection)
def fuse(records, strategy="keep_first"):
    # Detect which ids have duplicates
    seen_count = {}
    for r in records:
        seen_count[r["id"]] = seen_count.get(r["id"], 0) + 1
    conflicts = {id_ for id_, count in seen_count.items() if count > 1}

    if strategy == "keep_last":
        seen = {}
        for r in records:
            seen[r["id"]] = r
        result = []
        for r in seen.values():
            out = {**r, "fused": True}
            if r["id"] in conflicts:
                out["conflict"] = True
            result.append(out)
        return result

    seen = set()
    result = []
    for r in records:
        if r["id"] not in seen:
            seen.add(r["id"])
            out = {**r, "fused": True}
            if r["id"] in conflicts:
                out["conflict"] = True
            result.append(out)
    return result
