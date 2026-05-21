# Report Format

Canonical field order and formatting rules for bounded cycle reports.

## Canonical field order

```
HEAD:     <git commit hash>
TESTS:    <N passed | N passed, M failed | skipped>
FILES:    <comma-separated list of changed files>
PUSHED:   <yes | no>
RISKS:    <one-line risk summary | none>
```

Optional fields follow, in this order:

```
DURATION: <wall-clock elapsed, labeled as informational>
NOTES:    <single short sentence or none>
BLOCKERS: <description | none>
```

## Formatting expectations

1. One field per line
2. Field name followed by colon and single space
3. Values are one line only — no multiline field values
4. No markdown headers inside the report block
5. No bullet lists inside the report block
6. No code fences inside the report block
7. Total report length: 5–10 lines (mandatory fields only: 5 lines)

## Failure reporting rules

- If tests fail: `TESTS: N passed, M failed — <first failing test name>`
- If commit absent: `HEAD: none`
- If push was not attempted: `PUSHED: no`
- If scope was exceeded or ambiguous: `BLOCKERS: <reason>`
- Failure reports are complete reports — do not omit fields

## Deterministic language expectations

Use:
- "N passed" not "all tests passing"
- "no" not "not yet" or "skipped for now"
- "none" not "no known risks at this time"
- File paths verbatim, not paraphrased
- Commit hash verbatim (short form acceptable: 7 hex chars minimum)

Avoid:
- Hedged language ("should be", "appears to", "likely")
- Speculative risk statements ("might cause issues later")
- Roadmap language ("next we could", "future improvement")
- Architecture commentary in risk fields

## Truncation and line-limit discipline

- If FILES list exceeds one line: truncate to first 3 files + count remainder (`+N more`)
- If RISKS are complex: use one crisp sentence; defer detail to a separate artifact
- Reports exceeding 15 lines are non-conforming

## Required reporting after each bounded cycle

A report is required after:
- Any completed task (success or failure)
- Any bounded failure-stop
- Any scope rejection

A report is not required for:
- Clarifying questions mid-cycle
- Partial progress updates

## NOTES field usage

NOTES is for a single factual observation not captured by other fields. Examples:

- `NOTES: deferred D1 migration — requires fixture regeneration`
- `NOTES: test updated to reflect new canonical sort contract`
- `NOTES: none`

Do not use NOTES for speculation, roadmap items, or design proposals.
