from deterministic_message_id import generate_message_id
from local_model_runner import run_model
from message_bus import get_inbox, put_outbox

WORKER_REQUIRED = {"message_id", "candidate_id", "sender", "recipient", "role", "turn_number", "payload"}


def _validate_schema(msg: dict) -> None:
    missing = WORKER_REQUIRED - set(msg.keys())
    if missing:
        raise ValueError(f"Inbox message missing fields: {missing}")
    if not str(msg["message_id"]).startswith("msg_"):
        raise ValueError(f"message_id must start with 'msg_': {msg['message_id']!r}")
    if not isinstance(msg["turn_number"], int):
        raise ValueError("turn_number must be int")
    if not isinstance(msg["payload"], dict):
        raise ValueError("payload must be dict")


def _build_prompt(messages: list, max_context: int) -> str:
    bounded = messages[-max_context:] if len(messages) > max_context else messages
    lines = []
    for msg in bounded:
        role = msg.get("role", "user").upper()
        text = msg["payload"].get("text", "")
        lines.append(f"[{role}] {text}")
    return "\n".join(lines)


class DiAWorker:
    def __init__(self, worker_id: str, model_name: str = "stub", backend: str = "stub", max_context: int = 10):
        self.worker_id = worker_id
        self.model_name = model_name
        self.backend = backend
        self.max_context = max_context

    def run(self) -> list:
        messages = get_inbox(self.worker_id)
        replies = []

        for msg in messages:
            _validate_schema(msg)
            prompt = _build_prompt(messages, self.max_context)
            result = run_model(self.model_name, prompt, backend=self.backend)

            candidate_id = msg["candidate_id"]
            reply_turn = msg["turn_number"] + 1
            reply_id = generate_message_id(
                candidate_id=candidate_id,
                sender=self.worker_id,
                recipient=msg["sender"],
                role="assistant",
                turn_number=reply_turn,
            )
            reply = {
                "message_id": reply_id,
                "candidate_id": candidate_id,
                "sender": self.worker_id,
                "recipient": msg["sender"],
                "role": "assistant",
                "turn_number": reply_turn,
                "payload": {
                    "text": result["output_text"],
                    "model_name": result["model_name"],
                    "prompt_hash": result["prompt_hash"],
                    "output_hash": result["output_hash"],
                    "status": result["status"],
                },
            }
            put_outbox(reply)
            replies.append(reply)

        return replies
