# Transcript-Native Message Bus Plan

Baseline anchor: af32484

Goal:
Add replayable, schema-validated agent communication without changing ledger/replay semantics.

Non-goals:
- No new agents yet
- No UI
- No MCP
- No domain heuristics
- No mutation of existing baseline artifacts
- No change to hash-chain semantics

Phase 1:
Define a minimal transcript event schema:
- message_id
- run_id
- sender
- recipient
- role
- content
- references
- created_at
- parent_message_id
- metadata

Phase 2:
Validate transcript events independently from execution events.

Phase 3:
Append transcript events through the existing ledger writer.

Phase 4:
Replay transcript events deterministically and reconstruct conversation order.

Acceptance test:
A toy two-agent exchange can be appended, replayed, and reconstructed with byte-stable deterministic output.
