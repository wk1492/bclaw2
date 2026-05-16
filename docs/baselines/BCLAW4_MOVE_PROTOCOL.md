# BCLAW4 Move Protocol

Version: 1.0  
Schemas: `scheduler/task_packet.json`, `scheduler/agent_result.json`, `scheduler/window_registry.json`

---

## Rules

### 1. Ten-Move Rule

Each coordination session is divided into at most ten discrete moves.
A move is one task packet dispatched to one agent, producing one result.
Sessions that reach move ten without a terminal result must stop and
require operator review before continuing.

### 2. Drift Monitoring

Every agent result must include a `drift_risk` field: `none`, `low`,
`medium`, or `high`. Any result with `drift_risk` of `high` halts the
session immediately. The operator must inspect the ledger before the
next move is dispatched.

### 3. Single-Writer Invariant

At any moment only one agent holds write authority over the active
branch. The `window_registry` entry for every other agent must have
`state` set to `idle` or `waiting`. An agent must not modify files
while another agent's `state` is `active`.

### 4. Mandatory Test Reporting

Every agent result must populate `tests_run` with the count of test
cases executed. Zero is a valid value only when the move explicitly
forbids test execution (documented in `stop_condition`). A missing or
null `tests_run` is a protocol violation.

### 5. Unresolved Marking

`unresolved` in an agent result contains the structural unresolved
message IDs from the transcript at move close — messages whose declared
parent or reference edges point outside the event set. This field must
not be omitted. An empty list `[]` is the correct value when the
transcript graph has no dangling edges.

### 6. Stop-on-Failure

If `result` is `fail` or `stopped`, no further moves may be dispatched
automatically. The session halts. The `next_recommended_move` field
may suggest a recovery path for the operator, but the operator must
explicitly restart the scheduler.

### 7. Communication-Before-Computation

Before performing file modifications, an agent must append at least
one `transcript.message` event to the shared ledger declaring its
intent. Computation without a preceding communication event is a
protocol violation. This ensures the audit trail precedes any state
change.

---

## Schema Quick Reference

### TaskPacket (`scheduler/task_packet.json`)

| Field | Type | Description |
|---|---|---|
| `move_id` | string | Unique move identifier (`m01`, `m02`, …) |
| `assigned_agent` | string | Agent receiving this packet |
| `objective` | string | Plain-language goal |
| `allowed_files` | string[] | Glob patterns agent may touch |
| `forbidden_files` | string[] | Glob patterns agent must not touch |
| `autonomy_level` | enum | `supervised`, `semi-autonomous`, `autonomous` |
| `stop_condition` | string | Termination criterion |
| `requires_human_approval` | boolean | Gate before ledger close |
| `status` | enum | `pending`, `assigned`, `complete`, `failed`, `stopped` |

### AgentResult (`scheduler/agent_result.json`)

| Field | Type | Description |
|---|---|---|
| `move_id` | string | Move this result closes |
| `agent` | string | Agent that produced this result |
| `files_changed` | string[] | Files created or modified |
| `tests_run` | integer | Count of test cases executed |
| `result` | enum | `pass`, `fail`, `stopped` |
| `drift_risk` | enum | `none`, `low`, `medium`, `high` |
| `unresolved` | string[] | Structural unresolved message IDs |
| `next_recommended_move` | string\|null | Suggested next move or null |

### WindowRegistry (`scheduler/window_registry.json`)

| Field | Type | Description |
|---|---|---|
| `agent` | string | Agent identifier |
| `role` | enum | `proposer`, `critic`, `arbiter` |
| `active_task` | string\|null | Current move ID or null |
| `branch` | string | Git branch |
| `state` | enum | `idle`, `active`, `waiting`, `complete` |
