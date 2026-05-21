import hashlib
import json
from pathlib import Path

from transcript_event import make_transcript_event
from transcript_ledger import (
    append_transcript_event,
    load_ledger_lines,
    verify_mixed_ledger,
)
from transcript_topology import linearize_transcript_topology

TRANSCRIPT_EVENT_TYPE = "transcript.message"
RUN_ID = "bclaw4_mailbox_001"
VALID_RECIPIENTS = frozenset({"agent_a", "agent_b", "arbiter", "broadcast"})
_BASE_DATE = "2026-05-15"


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _seq_ts(seq: int) -> str:
    h = 11 + seq // 3600
    m = (seq % 3600) // 60
    s = seq % 60
    return f"{_BASE_DATE}T{h:02d}:{m:02d}:{s:02d}+00:00"


class Mailbox:
    def __init__(self, ledger_path):
        self.ledger_path = Path(ledger_path)
        self.run_id = RUN_ID

    def _transcript_events(self) -> list:
        records = load_ledger_lines(self.ledger_path)
        return [r for r in records if r.get("event_type") == TRANSCRIPT_EVENT_TYPE]

    def _next_seq(self) -> int:
        return len(self._transcript_events())

    def append_message(
        self,
        sender: str,
        recipient: str,
        role: str,
        content: str,
        references: list = None,
    ) -> dict:
        if recipient not in VALID_RECIPIENTS:
            raise ValueError(
                f"invalid recipient {recipient!r}; must be one of {sorted(VALID_RECIPIENTS)}"
            )
        created_at = _seq_ts(self._next_seq())
        event = make_transcript_event(
            run_id=self.run_id,
            sender=sender,
            recipient=recipient,
            role=role,
            content=content,
            created_at=created_at,
            references=references or [],
        )
        return append_transcript_event(event, self.ledger_path)

    def read_mailbox(self, agent_id: str) -> list:
        events = self._transcript_events()
        inbox = [e for e in events if e.get("recipient") == agent_id]
        return sorted(inbox, key=lambda e: e["message_id"])

    def read_broadcasts(self) -> list:
        events = self._transcript_events()
        broadcasts = [e for e in events if e.get("recipient") == "broadcast"]
        return sorted(broadcasts, key=lambda e: e["message_id"])

    def reconstruct_conversation(self) -> list:
        return linearize_transcript_topology(self._transcript_events())

    def summary(self) -> dict:
        events = self._transcript_events()
        linearized = linearize_transcript_topology(events)
        order = [e["message_id"] for e in linearized]
        topology_hash = _sha256(_canonical(order))
        chain = verify_mixed_ledger(self.ledger_path)

        summary_body = {
            "run_id": self.run_id,
            "message_count": len(events),
            "order": order,
            "topology_hash": topology_hash,
        }
        summary_id = "mbx_" + _sha256(_canonical(summary_body))[:24]

        return {
            "summary_id": summary_id,
            "run_id": self.run_id,
            "ledger_path": str(self.ledger_path),
            "message_count": len(events),
            "order": order,
            "topology_hash": topology_hash,
            "chain_ok": chain.get("ok", False),
        }
