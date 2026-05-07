from ledger_event_status import classify_candidate_results, is_fatal_event_status

def test_valid_results_are_ok():
    assert classify_candidate_results([{"valid": True}]) == "ok"

def test_invalid_candidate_is_validation_failed_not_fatal():
    status = classify_candidate_results([{"valid": False, "error": "bad candidate"}])
    assert status == "validation_failed"
    assert is_fatal_event_status(status) is False

def test_runtime_and_tamper_are_fatal():
    assert is_fatal_event_status("runtime_error") is True
    assert is_fatal_event_status("tamper_detected") is True

if __name__ == "__main__":
    test_valid_results_are_ok()
    test_invalid_candidate_is_validation_failed_not_fatal()
    test_runtime_and_tamper_are_fatal()
    print("PASS: ledger event status boundary")
