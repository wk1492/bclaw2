from datetime import datetime
from pathlib import Path
import json
import re
from typing import Literal

MESSAGE_TYPES = Literal[
    "candidate_proposal",
    "validation_result",
    "execution_proposal",
    "patch_proposal",
    "edge_proposal",
    "node_proposal",
    "alert",
    "ledger_summary",
    "human_approval_request",
]


class AgentMessage(dict):
    """Lightweight validated message structure."""

    @staticmethod
    def new(
        agent: str,
        msg_type: MESSAGE_TYPES,
        payload: dict,
        session_id: str = "bclaw2_default",
        metadata: dict | None = None,
    ) -> dict:
        now = datetime.utcnow().isoformat() + "Z"
        message_id = f"msg_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{agent.lower()}_{msg_type[:4]}"

        msg = {
            "message_id": message_id,
            "timestamp": now,
            "agent": agent.lower(),
            "session_id": session_id,
            "type": msg_type,
            "payload": payload,
            "metadata": metadata or {},
        }
        AgentMessage.validate(msg)
        return msg

    @staticmethod
    def validate(msg: dict) -> None:
        required = ["message_id", "timestamp", "agent", "session_id", "type", "payload"]
        for field in required:
            if field not in msg:
                raise ValueError(f"Missing required field: {field}")

        if not re.match(r"^msg_\d{8}_\d{6}_", msg["message_id"]):
            raise ValueError("message_id must follow msg_YYYYMMDD_HHMMSS_ format")

        if msg["type"] not in MESSAGE_TYPES.__args__:  # type: ignore
            raise ValueError(f"Unknown message type: {msg['type']}")


def example_edge_proposal() -> dict:
    return AgentMessage.new(
        agent="grok",
        msg_type="edge_proposal",
        session_id="bclaw2_horse_racing_001",
        payload={
            "edge_id": "E061",
            "from_node_id": "N001",
            "to_node_id": "OUTCOME_NODE",
            "causal_reason": "Early pace pressure increases late fatigue in routes.",
            "proposed_weight": 0.79,
            "proposed_confidence": 0.83,
            "supporting_evidence": ["historical race data", "replay patterns"],
        },
        metadata={
            "confidence": 0.81,
            "rationale_strength": "strong",
            "suggested_action": "add",
            "target_graph_version": "v0.3",
        },
    )


def example_candidate_proposal() -> dict:
    return AgentMessage.new(
        agent="grok",
        msg_type="candidate_proposal",
        payload={
            "candidate_id": "candidate-20260506-004",
            "proposed_action": "Implement agent_message_schema.py with Pydantic-style validation",
            "rationale": "Standardizes all inter-agent communication for better traceability and safety.",
            "risk_notes": "Very low - schema + examples only",
        },
    )


def save_examples():
    Path("message_examples.jsonl").write_text(
        json.dumps(example_edge_proposal()) + "\n"
        + json.dumps(example_candidate_proposal()) + "\n"
    )
    print("Saved message_examples.jsonl")


if __name__ == "__main__":
    save_examples()
    msg = example_edge_proposal()
    AgentMessage.validate(msg)
    print("PASS: all schemas valid")
    print(f"Message ID: {msg['message_id']}")
    print(f"Type: {msg['type']}")
