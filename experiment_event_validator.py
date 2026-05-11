class ExperimentEventValidationError(ValueError):
    pass


def _require(d, key, path=""):
    if key not in d:
        raise ExperimentEventValidationError(f"Missing required field: {path}{key}")
    return d[key]


def validate_experiment_event(event):
    if not isinstance(event, dict):
        raise ExperimentEventValidationError("Event must be a dict")

    if _require(event, "type") != "experiment_result":
        raise ExperimentEventValidationError("type must be experiment_result")

    if _require(event, "event_status") != "ok":
        raise ExperimentEventValidationError("event_status must be ok")

    for key in ["candidate_id", "task_id", "action"]:
        value = _require(event, key)
        if not isinstance(value, str) or not value:
            raise ExperimentEventValidationError(f"{key} must be a non-empty string")

    experiment = _require(event, "experiment")
    if not isinstance(experiment, dict):
        raise ExperimentEventValidationError("experiment must be a dict")

    name = _require(experiment, "name", "experiment.")
    if name != "underperformance_experiment":
        raise ExperimentEventValidationError("experiment.name must be underperformance_experiment")

    summary = _require(experiment, "summary", "experiment.")
    if not isinstance(summary, dict):
        raise ExperimentEventValidationError("experiment.summary must be a dict")

    contract_id = _require(summary, "contract_id", "experiment.summary.")
    primary_metric = _require(summary, "primary_metric", "experiment.summary.")
    value = _require(summary, "value", "experiment.summary.")

    if contract_id != "underperformance_v1":
        raise ExperimentEventValidationError("contract_id must be underperformance_v1")

    if primary_metric != "precision_underperformed_true":
        raise ExperimentEventValidationError("primary_metric must be precision_underperformed_true")

    if not isinstance(value, (int, float)):
        raise ExperimentEventValidationError("experiment.summary.value must be numeric")

    return event


validate_experiment_result_event = validate_experiment_event
