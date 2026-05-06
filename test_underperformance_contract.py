import json
from pathlib import Path

REQUIRED_KEYS = [
    "contract_id",
    "task",
    "inputs",
    "odds_to_expected_band",
    "outcome_label",
    "metrics",
    "primary_metric",
    "constraints",
    "allowed_loop",
]

def test_underperformance_contract_v1():
    path = Path("evaluation_contracts/underperformance_v1.json")
    contract = json.loads(path.read_text())

    for key in REQUIRED_KEYS:
        assert key in contract

    assert contract["contract_id"] == "underperformance_v1"
    assert contract["primary_metric"] == "precision_underperformed_true"
    assert contract["allowed_loop"] == "predict_observe_evaluate_log_only"
    assert contract["odds_to_expected_band"]["locked"] is True
    assert contract["outcome_label"]["margin_locked"] is True
    assert "no automatic weight updates" in contract["constraints"]

if __name__ == "__main__":
    test_underperformance_contract_v1()
    print("PASS: underperformance evaluation contract v1")
