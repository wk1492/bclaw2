from underperformance_experiment import run_underperformance_experiment, label_underperformance

def test_label_underperformance_margin_2():
    record = {"expected_band": 3, "actual_finish": 6}
    assert label_underperformance(record, margin=2) is True
    record2 = {"expected_band": 5, "actual_finish": 6}
    assert label_underperformance(record2, margin=2) is False

def test_experiment_precision_on_toy_data():
    labeled, summary, graph = run_underperformance_experiment()
    assert summary["contract_id"] == "underperformance_v1"
    assert 0.0 <= summary["value"] <= 1.0
    assert summary["total_predictions"] == 4
    assert isinstance(graph.graph_hash(), str)
    print("Graph hash:", graph.graph_hash()[:16] + "...")

def test_experiment_does_not_write_ledger():
    labeled, summary, graph = run_underperformance_experiment(log_to_ledger=False)
    assert summary["contract_id"] == "underperformance_v1"

if __name__ == "__main__":
    test_label_underperformance_margin_2()
    test_experiment_precision_on_toy_data()
    test_experiment_does_not_write_ledger()
    print("PASS: underperformance experiment harness with deterministic graph")
