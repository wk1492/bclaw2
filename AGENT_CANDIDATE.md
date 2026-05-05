# BCLAW2 Agent Candidate Contract

## Purpose

Any output from an agent (GPT, Claude, Grok, or other model) that proposes a change to the system must be structured as a **candidate record** before it can enter the BCLAW2 pipeline. Agents generate candidates only — they do not execute changes directly.

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier for this candidate (e.g. `cand_001`) |
| `source_model` | string | Model that generated the candidate (e.g. `"gpt-4o"`, `"claude-sonnet"`, `"grok-2"`) |
| `task_id` | string | Reference to the directed task this candidate responds to |
| `proposed_action` | string | Plain-text description of the exact change proposed |
| `rationale` | string | Why this change is being proposed, using only existing verified signals |
| `evidence` | string | Supporting signal or test result from the current system state |
| `risk_notes` | string | Known risks, unreachable paths, or open questions |
| `status` | string | One of: `"proposed"`, `"evaluated"`, `"approved"`, `"rejected"`, `"executed"` |

## Lifecycle

1. **Agent generates candidate** — structured as above, `status: "proposed"`
2. **BCLAW2 evaluates/fuses candidates** — runs candidates through evaluation pipeline, updates `status` to `"evaluated"`
3. **Human approves execution** — human relay reviews and sets `status` to `"approved"` or `"rejected"`
4. **Execution occurs** — only `"approved"` candidates are executed; `status` updated to `"executed"`

## Hard Rules

- Agents generate candidates only. No agent executes a change directly.
- BCLAW2 evaluates and fuses candidates. No candidate self-selects for execution.
- Humans approve execution. No automated execution without explicit human approval.
- Every executed change must have a corresponding candidate record with a complete audit trail.
- Candidates must reference a specific `task_id` — open-ended or self-directed candidates are not valid.
