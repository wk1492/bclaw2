def validate_experiment_result_event(event):
    if event.get("type") != "experiment_result":
        raise ValueError("experiment event type must be experiment_result")

    if event.get("event_status") != "ok":
        raise ValueError("experiment_result event_status must be ok")

    for key in ["candidate_id", "task_id", "action", "experiment"]:
        if not event.get(key):
            raise ValueError(f"missing required experiment_result field: {key}")

    experiment = event["experiment"]
    if experiment.get("name") != "underperformance_experiment":
        raise ValueError("experiment.name must be underperformance_experiment")

    summary = experiment.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("experiment.summary must be a dict")

    for key in ["contract_id", "primary_metric", "value"]:
        if key not in summary:
            raise ValueError(f"missing experiment.summary field: {key}")

    if summary["contract_id"] != "underperformance_v1":
        raise ValueError("summary.contract_id must be underperformance_v1")

    return event
