from agent_alerts import build_candidate_alerts


def test_invalid_candidate_creates_alert():
    validations = [{"id": "bad-001", "valid": False}]
    alerts = build_candidate_alerts(validations)
    assert len(alerts) == 1
    assert alerts[0]["level"] == "ALERT"
    assert alerts[0]["candidate_id"] == "bad-001"


def test_valid_candidate_creates_no_alert():
    validations = [{"id": "good-001", "valid": True}]
    alerts = build_candidate_alerts(validations)
    assert alerts == []


if __name__ == "__main__":
    test_invalid_candidate_creates_alert()
    test_valid_candidate_creates_no_alert()
    print("PASS: alerting layer detects invalid candidates")
