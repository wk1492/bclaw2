import json
from pathlib import Path

from agent_message_schema import AgentMessage

MESSAGE_FILE = Path("message_queue.jsonl")


def load_messages():
    if not MESSAGE_FILE.exists():
        return []

    messages = []
    for line in MESSAGE_FILE.read_text().splitlines():
        if not line.strip():
            continue
        msg = json.loads(line)
        AgentMessage.validate(msg)
        messages.append(msg)

    return messages


def classify_messages(messages):
    classified = {
        "edge_proposals": [],
        "node_proposals": [],
        "candidate_proposals": [],
        "alerts": [],
        "other": [],
    }

    for msg in messages:
        msg_type = msg.get("type")
        if msg_type == "edge_proposal":
            classified["edge_proposals"].append(msg)
        elif msg_type == "node_proposal":
            classified["node_proposals"].append(msg)
        elif msg_type == "candidate_proposal":
            classified["candidate_proposals"].append(msg)
        elif msg_type == "alert":
            classified["alerts"].append(msg)
        else:
            classified["other"].append(msg)

    return classified


if __name__ == "__main__":
    messages = load_messages()
    classified = classify_messages(messages)
    print(json.dumps({
        "message_count": len(messages),
        "edge_proposals": len(classified["edge_proposals"]),
        "node_proposals": len(classified["node_proposals"]),
        "candidate_proposals": len(classified["candidate_proposals"]),
        "alerts": len(classified["alerts"]),
        "other": len(classified["other"]),
    }, indent=2))
