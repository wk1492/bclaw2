from underperformance_experiment import (
    TOY_RACES,
    label_underperformance,
    run_underperformance_experiment,
)


def test_label_underperformance_margin_2():
    r = {"expected_band": 2, "actual_finish": 5}
    assert label_underperformance(r, margin=2) is True
    assert label_underperformance(r, margin=4) is False


def test_experiment_precision_on_toy_data():
    labeled, summary = run_underperformance_experiment(
        races=TOY_RACES,
        margin=2,
        log_to_ledger=False,
    )

    # Sanity: all races labeled
    assert len(labeled) == len(TOY_RACES)

    # Compute expected precision manually for the fixed TOY_RACES and margin=2.
    expected_labeled = []
    for r in TOY_RACES:
        true_under = label_underperformance(r, margin=2)
        pred = bool(r["predicted_underperformed"])
        expected_labeled.append({"pred": pred, "true": true_under, "correct": pred and true_under})

    predicted_true = [x for x in expected_labeled if x["pred"]]
    correct_true = [x for x in predicted_true if x["correct"]]
    if not predicted_true:
        expected_precision = 0.0
    else:
        expected_precision = len(correct_true) / len(predicted_true)

    assert summary["contract_id"] == "underperformance_v1"
    assert summary["primary_metric"] == "precision_underperformed_true"
    assert summary["total_predictions"] == len(TOY_RACES)
    assert summary["predicted_true_count"] == len(predicted_true)
    assert abs(summary["value"] - expected_precision) < 1e-9


def test_experiment_logs_to_ledger_without_error():
    # This just exercises the ledger path; verification is done by existing harnesses.
    _, summary = run_underperformance_experiment(
        races=TOY_RACES,
        margin=2,
        log_to_ledger=True,
    )
    assert summary["contract_id"] == "underperformance_v1"


if __name__ == "__main__":
    test_label_underperformance_margin_2()
    test_experiment_precision_on_toy_data()
    test_experiment_logs_to_ledger_without_error()
    print("PASS: underperformance experiment harness")
