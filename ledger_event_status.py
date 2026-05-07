VALID_EVENT_STATUSES = {
    "ok",
    "validation_failed",
    "runtime_error",
    "tamper_detected",
}

FATAL_EVENT_STATUSES = {
    "runtime_error",
    "tamper_detected",
}

def classify_candidate_results(results):
    if any(not r.get("valid", False) for r in results):
        return "validation_failed"
    return "ok"

def is_fatal_event_status(status):
    return status in FATAL_EVENT_STATUSES
