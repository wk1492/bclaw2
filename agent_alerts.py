def build_candidate_alerts(validations):
    alerts = []
    for item in validations:
        if not item.get("valid", False):
            alerts.append({
                "level": "ALERT",
                "type": "invalid_candidate",
                "candidate_id": item.get("id", "unknown"),
                "message": "Candidate failed validation",
            })
    return alerts


def print_alerts(alerts):
    for alert in alerts:
        print("{}: {} {} - {}".format(alert["level"], alert["type"], alert["candidate_id"], alert["message"]))
