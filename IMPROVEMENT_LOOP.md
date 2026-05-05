# BCLAW2 Improvement Loop

## Current Verified Loop

1. **Human** relays model outputs between models
2. **GPT** sequences the next step
3. **Claude** implements and verifies in-session
4. **Grok** reviews and critiques
5. **Tests** determine acceptance — nothing is verified without a passing test
6. **CONTRACT.md** records only verified, tested behavior

## What This Is Not

- This is **not** recursive self-improvement (RSI)
- No autonomous model-to-model communication
- No automatic code modification without human relay
- No self-selection of changes without tests
- No model decides what to build without explicit human instruction

## What RSI Would Require

- Automated critique loop (no human relay)
- Automated test execution and result routing
- Selection mechanism with rollback on failure
- Persistent audit trail of all changes and rejections
- Defined stopping criteria and safety bounds

None of the above are present in the current system.
