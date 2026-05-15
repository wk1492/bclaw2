# BCLAW4 Chaos Lab — Experiment 001

Branch: bclaw4-chaos-lab-001
Date: 2026-05-15

## Goal

Execute 10 bounded, deterministic moves using the existing BCLAW2/BCLAW3
transcript substrate (ledger append, topology, chain verification, replay).
No production files mutated. No real model calls. No FCM writes.

## Agents

| Agent | Role |
|---|---|
| bclaw4_runner | proposer / reply author |
| bclaw4_critic | critique author |
| bclaw4_arbiter | arbiter / synthesizer |

## Move DAG

```
m01 (proposal)
├── m02 (reply)
│   └── m03 (reply)
│       └── m04 (reply)
└── m05 (critique, refs=[m04])
m06 (arbiter, refs=[m01..m05])   ← new root
└── m07 (proposal)
    ├── m08 (critique)
    └── m09 (reply, refs=[m08])
m10 (arbiter, refs=[m06..m09])   ← final root
```

## Invariants

1. Chain OK after all 10 appends
2. Replay returns exactly 10 events
3. Topology has exactly 10 nodes, 0 orphaned
4. Both arbiter moves appear after all referenced events in linearized order
5. summary_id is content-addressed and deterministic across runs
