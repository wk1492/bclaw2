from experiment_event_validator import validate_experiment_result_event

def test_valid_underperformance_experiment_event():
    event = {
        "type": "experiment_result",
        "event_status": "ok",
        "candidate_id": "test_underperformance_001",
        "task_id": "underperformance_v1",
        "action": "Run manual underperformance experiment under locked v1 contract",
        "experiment": {
            "name": "underperformance_experiment",
            "summary": {
                "contract_id": "underperformance_v1",
                "primary_metric": "precision_underperformed_true",
                "value": 0.6666666666666666,
            },
        },
    }

    assert validate_experiment_result_event(event) == event

if __name__ == "__main__":
    test_valid_underperformance_experiment_event()
    print("PASS: experiment_result event schema")
