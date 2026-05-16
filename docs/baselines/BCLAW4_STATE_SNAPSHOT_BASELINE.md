# BCLAW4 State Snapshot Baseline

Branch: bclaw4-chaos-lab-001
Experiment: 005
Date: 2026-05-15

## Frozen Artifact

`artifacts/baselines/bclaw4_state_snapshot_001.json`

artifact_id: `db54a2a715b7cbff9b75a92a051e0be9293b705025de2d1d68969c4512a54b72`
transcript_hash: `7bebd5d9431af4a8c4f2e63b8b6e9431d80bdc8e8c56ff5b02185b39bc8aafa1`

## Exchange

```
proposal  agent_a → broadcast        "Proposal: assert causal edge fatigue->error_rate..."
critique  agent_b → agent_a          "Challenge: weight=0.6 overstated..."
critique  agent_c → agent_a          "Challenge: confounder workload_history not controlled"
arbiter   agent_arbiter → broadcast  "Arbiter: both critiques accepted; proposal deferred..."
```

## Frozen Derived State

```json
{
  "proposal_count":   1,
  "critique_count":   2,
  "accepted_count":   2,
  "rejected_count":   1,
  "unresolved_count": 0,
  "participants":     ["agent_a","agent_arbiter","agent_b","agent_c"],
  "last_status":      "arbiter",
  "thread_ids":       ["tmsg_529d...","tmsg_536b...","tmsg_6bc5...","tmsg_980b..."],
  "transcript_hash":  "7bebd5d9..."
}
```

## Regression Contract

Any future change to `reduce_transcript_state` that alters this artifact is a breaking change.
Update this file and the artifact together; never silently overwrite.
