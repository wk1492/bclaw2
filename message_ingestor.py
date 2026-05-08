import json
from pathlib import Path
from agent_message_schema import AgentMessage

QUEUE_FILE = Path("message_queue.jsonl")
PROCESSED_DIR = Path("processed_messages")
PROCESSED_DIR.mkdir(exist_ok=True)

def load_messages():
    if not QUEUE_FILE.exists():
        return []
    messages = []
    with QUEUE_FILE.open("r") as f:
        for line in f:
            if line.strip():
                messages.append(json.loads(line))
    return messages

def classify_messages(messages):
    classified = {
        "edge_proposals": [],
        "node_proposals": [],
        "candidate_proposals": [],
        "alerts": [],
        "other": []
    }
    for msg in messages:
        try:
            AgentMessage.validate(msg)
            t = msg.get("type")
            if t == "edge_proposal":
                classified["edge_proposals"].append(msg)
            elif t == "node_proposal":
                classified["node_proposals"].append(msg)
            elif t == "candidate_proposal":
                classified["candidate_proposals"].append(msg)
            elif t == "alert":
                classified["alerts"].append(msg)
            else:
                classified["other"].append(msg)
        except Exception as e:
            print(f"WARNING: invalid message {msg.get('message_id')}: {e}")
    return classified

def archive_message(msg):
    archive_file = PROCESSED_DIR / f"{msg.get('message_id', 'unknown')}.json"
    archive_file.write_text(json.dumps(msg, indent=2))

def main():
    if not QUEUE_FILE.exists() or QUEUE_FILE.stat().st_size == 0:
        print("No messages in queue")
        return

    messages = load_messages()
    if not messages:
        print("No messages in queue")
        return

    classified = classify_messages(messages)

    print(json.dumps({
        "message_count": len(messages),
        "edge_proposals": len(classified["edge_proposals"]),
        "node_proposals": len(classified["node_proposals"]),
        "candidate_proposals": len(classified["candidate_proposals"]),
        "alerts": len(classified["alerts"]),
        "other": len(classified["other"]),
    }, indent=2))

    archived = []
    try:
        for msg in messages:
            archive_message(msg)
            archived.append(msg.get("message_id", "unknown"))
    except Exception as e:
        print(f"ALERT: archive failed; queue preserved: {e}")
        print(f"Archived before failure: {len(archived)}/{len(messages)}")
        return

    QUEUE_FILE.write_text("")
    print(f"Processed and archived {len(messages)} messages")

if __name__ == "__main__":
    main()
