# Transcript Event Contract

Baseline anchor: 88e9eb2

Purpose:
Define the minimal event shape for replayable agent-to-agent communication.

Rules:
- Transcript events are data, not behavior.
- Transcript events must be schema validated before append.
- Transcript events must be replayable through existing ledger mechanics.
- Transcript events must not alter execution-event semantics.
- Transcript ordering must be reconstructable deterministically.

Minimal event fields:
- event_type: "transcript.message"
- message_id: stable unique string
- run_id: stable run identifier
- sender: agent/model/system identifier
- recipient: agent/model/system identifier or "broadcast"
- role: speaker role such as "proposal", "critique", "reply", "arbiter", or "system"
- content: exact message payload
- references: list of referenced message_ids or event ids
- parent_message_id: optional parent message id
- created_at: deterministic timestamp or supplied timestamp
- metadata: JSON object

Canonical serialization:
Transcript events must use the same canonical JSON behavior as existing ledger events:
- sort_keys=True where applicable
- separators=(",", ":")
- no implicit mutation during replay

Acceptance test:
Given two transcript.message events:
1. agent_a proposes a causal edge
2. agent_b critiques that proposal

The system must:
- validate both events
- append both events
- replay both events
- reconstruct parent/child ordering
- produce byte-stable output across repeated runs
