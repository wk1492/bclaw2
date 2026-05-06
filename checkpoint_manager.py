import json
from datetime import UTC, datetime
from pathlib import Path

from state_serializer import state_hash


CHECKPOINT_DIR = Path("checkpoints")
SCHEMA_VERSION = "1"
SERIALIZER_VERSION = "1"


def utc_now():
    return datetime.now(UTC).isoformat()


class CheckpointManager:
    def __init__(self, checkpoint_dir=CHECKPOINT_DIR):
        self.dir = Path(checkpoint_dir)
        self.dir.mkdir(exist_ok=True)

    def create_checkpoint(
        self,
        checkpoint_type,
        state,
        checkpoint_id=None,
        parent_hash=None,
        ledger_offset=-1,
    ):
        checkpoint_id = checkpoint_id or f"cp_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{checkpoint_type}"

        envelope = {
            "checkpoint_id": checkpoint_id,
            "timestamp": utc_now(),
            "checkpoint_type": checkpoint_type,
            "schema_version": SCHEMA_VERSION,
            "serializer_version": SERIALIZER_VERSION,
            "parent_hash": parent_hash,
            "ledger_offset": ledger_offset,
            "state_hash": state_hash(state),
            "state": state,
        }

        path = self.dir / f"{checkpoint_id}.json"

        with path.open("w", encoding="utf-8") as f:
            json.dump(envelope, f, indent=2, sort_keys=True)

        return path

    def load_checkpoint(self, path):
        with Path(path).open("r", encoding="utf-8") as f:
            data = json.load(f)

        expected = data.get("state_hash")
        actual = state_hash(data.get("state"))

        if actual != expected:
            raise ValueError(f"checkpoint state hash mismatch: expected {expected}, got {actual}")

        return data

    def latest_checkpoint(self):
        files = sorted(self.dir.glob("*.json"))
        if not files:
            return None
        return files[-1]


if __name__ == "__main__":
    mgr = CheckpointManager()

    state = {
        "graph": {
            "nodes": {"N001": {"activation": 0.7}},
            "edges": {"E001": {"weight": 0.8}},
        }
    }

    path = mgr.create_checkpoint("graph_state", state)
    restored = mgr.load_checkpoint(path)

    print("PASS: checkpoint envelope verified")
    print(restored["checkpoint_id"])
    print(restored["state_hash"])
