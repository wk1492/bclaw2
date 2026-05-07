import json
from pathlib import Path
from serializer_registry import canonical_serialize
from execution_ledger import append_run, build_run_record


TOY_RACES = [
    {
        "race_id": "R1",
        "horse_id": "H1",
        "odds": 2.0,
        "expected_band": 2,
        "actual_finish": 5,
        "predicted_underperformed": True,
    },
    {
        "race_id": "R1",
        "horse_id": "H2",
        "odds": 5.0,
        "expected_band": 4,
        "actual_finish": 3,
        "predicted_underperformed": True,
    },
    {
        "race_id": "R2",
        "horse_id": "H3",
        "odds": 3.0,
        "expected_band": 3,
        "actual_finish": 6,
        "predicted_underperformed": True,
    },
    {
        "race_id": "R2",
        "horse_id": "H4",
        "odds": 10.0,
        "expected_band": 7,
        "actual_finish": 7,
        "predicted_underperformed": False,
    },
]


def label_underperformance(record, margin=2):
    expected = record["expected_band"]
    actual = record["actual_finish"]
    return (actual - expected) >= margin


def run_underperformance_experiment(
    races=None,
    contract_id="underperformance_v1",
    margin=2,
    log_to_ledger=True,
):
    if races is None:
        races = TOY_RACES

    labeled = []
    for r in races:
        true_under = label_underperformance(r, margin=margin)
        pred = bool(r["predicted_underperformed"])
        labeled.append(
            {
                "race_id": r["race_id"],
                "horse_id": r["horse_id"],
                "predicted_underperformed": pred,
                "true_underperformed": true_under,
                "correct": pred and true_under,
            }
        )

    predicted_true = [x for x in labeled if x["predicted_underperformed"]]
    if not predicted_true:
        precision = 0.0
    else:
        correct_true = [x for x in predicted_true if x["correct"]]
        precision = len(correct_true) / len(predicted_true)

    summary = {
        "contract_id": contract_id,
        "primary_metric": "precision_underperformed_true",
        "value": precision,
        "total_predictions": len(labeled),
        "predicted_true_count": len(predicted_true),
    }

    if log_to_ledger:
        record = build_run_record(
            run_type="underperformance_experiment",
            input_data={"races": races},
            output_data={"labeled": labeled, "summary": summary},
            metadata={
                "contract_id": contract_id,
                "loop": "predict_observe_evaluate_log_only",
            },
        )
        # Ledger writes are owned by agent_loop.py / LedgerWriter only.
        # This harness computes deterministic results but does not append directly.

    return labeled, summary


def main():
    _, summary = run_underperformance_experiment()
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
