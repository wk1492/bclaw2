from ledger_analytics import summarize_ledger

def test_ledger_summary_runs():
    summary = summarize_ledger()
    assert "total_entries" in summary
    assert "entry_types" in summary
    assert "pass_rate" in summary

if __name__ == "__main__":
    test_ledger_summary_runs()
    print("PASS: ledger analytics summarizes ledger")
