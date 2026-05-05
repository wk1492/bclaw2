import json
from pathlib import Path

CANDIDATES_FILE = Path("agent_candidates.json")

DONE_STATUSES = {"implemented", "archived"}
ACTIVE_STATUSES = {"proposed", "validated"}

def load_candidates():
    if not CANDIDATES_FILE.exists():
        return []
    return json.loads(CANDIDATES_FILE.read_text())

def candidate_map(candidates):
    return {c.get("id"): c for c in candidates}

def dependency_status(candidate, by_id):
    deps = candidate.get("dependencies", [])
    missing = []
    incomplete = []

    for dep_id in deps:
        dep = by_id.get(dep_id)
        if dep is None:
            missing.append(dep_id)
        elif dep.get("status") not in DONE_STATUSES:
            incomplete.append(dep_id)

    return missing, incomplete

def plan_execution(candidates=None):
    candidates = candidates if candidates is not None else load_candidates()
    by_id = candidate_map(candidates)

    ready = []
    blocked = []

    for c in candidates:
        if c.get("status") not in ACTIVE_STATUSES:
            continue

        missing, incomplete = dependency_status(c, by_id)
        item = {
            "id": c.get("id"),
            "priority": c.get("priority", 5),
            "task_id": c.get("task_id"),
            "proposed_action": c.get("proposed_action"),
        }

        if missing or incomplete:
            item["blocked_by_missing"] = missing
            item["blocked_by_incomplete"] = incomplete
            blocked.append(item)
        else:
            ready.append(item)

    ready.sort(key=lambda x: (x.get("priority", 5), x.get("id", "")))

    return {"ready": ready, "blocked": blocked}

if __name__ == "__main__":
    print(json.dumps(plan_execution(), indent=2))
