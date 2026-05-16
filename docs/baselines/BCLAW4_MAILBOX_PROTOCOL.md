# BCLAW4 Mailbox Protocol

Branch: bclaw4-chaos-lab-001
Experiment: 002
Date: 2026-05-15

## Design Principle

Every inter-agent message is a `transcript.message` ledger event.
The ledger is the communication source of truth.
No in-memory state, no direct function calls, no hidden coupling.

## Routing

| Recipient | Meaning |
|---|---|
| `agent_a` | addressed to agent_a only |
| `agent_b` | addressed to agent_b only |
| `arbiter` | addressed to arbiter only |
| `broadcast` | visible to all via `read_broadcasts()` |

## API

```
append_message(sender, recipient, role, content, references=None) → decorated event
read_mailbox(agent_id) → events where recipient==agent_id, sorted by (created_at, message_id)
read_broadcasts() → events where recipient=="broadcast", sorted by (created_at, message_id)
reconstruct_conversation() → all events in linearized topology order
summary() → JSON-safe dict with summary_id, topology_hash, chain_ok
```

## Invariants

- All messages are valid `transcript.message` events.
- Timestamps are seq-derived (no runtime clocks).
- A fresh `Mailbox` instance reading the same ledger reconstructs identical mailboxes.
- `replay_execution_events` returns `[]` — mailbox events are transparent to execution layer.
- Chain hash passes `verify_ledger` after every append.
