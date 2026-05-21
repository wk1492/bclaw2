# task_queue

Bounded execution cycle management for the BCLAW2 deterministic substrate.

## Purpose

The task queue defines the contract for scoped, auditable work cycles. Each cycle has a fixed scope, a bounded file-change limit, and produces a mandatory report upon completion.

## Reports are audit artifacts

Every completed cycle produces a report. Reports are:

- Written in the conversation or appended to a log
- Concise — no roadmap commentary, no speculation
- Deterministic in wording — describe what happened, not what might happen
- Compatible with replay-safe philosophy: no timestamps, no wall-clock durations unless explicitly labeled OPTIONAL

Reports are not design documents. They are not proposals. They are records of what occurred.

## Report contract

See [REPORT_FORMAT.md](REPORT_FORMAT.md) for the full field specification.

Mandatory fields after every bounded cycle:

```
HEAD:
TESTS:
FILES:
PUSHED:
RISKS:
```

Optional fields:

```
DURATION:
NOTES:
BLOCKERS:
```

## Cycle constraints

| Constraint | Limit |
|---|---|
| Max files changed | 3 |
| Max LOC delta | ~200 lines |
| Max autonomous repair attempts | 2 |
| Max response length | 100 lines |

## Conciseness requirements

- No architecture redesign proposals inside reports
- No speculative improvements
- No recaps unless task completed
- Deterministic language preferred over hedged language
- Reports describe outcomes, not intentions

## Terminology

- **Cycle**: one bounded unit of work from task receipt to final report
- **Report**: mandatory structured output produced at cycle end
- **HEAD**: git commit hash at cycle completion
- **Bounded failure-stop**: a cycle that halted due to repeated test failure or scope ambiguity
