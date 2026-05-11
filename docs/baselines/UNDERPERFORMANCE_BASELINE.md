# Underperformance Baseline

Baseline commit: ca0a2fc

Status:
- 132 tests passing
- Ledger/replay invariants verified
- Serialization consistent
- Mutable snapshot aliasing fixed
- underperformance_experiment.py deterministic

Canonical output artifact:
- artifacts/baselines/underperformance_ca0a2fc.txt

Expected experiment summary:
- precision = 0.667
- predictions = 4

Purpose:
This baseline is the regression truth for future BCLAW2 architectural changes. Any later agent, critique, arbitration, FCM, or message-bus work must preserve deterministic replay behavior against this checkpoint unless intentionally migrated.
