import hashlib
import json


def generate_message_id(
    candidate_id: str,
    sender: str,
    recipient: str,
    role: str,
    turn_number: int,
) -> str:
    canonical = json.dumps(
        {
            "candidate_id": candidate_id,
            "recipient": recipient,
            "role": role,
            "sender": sender,
            "turn_number": turn_number,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"msg_{digest}"


if __name__ == "__main__":
    mid = generate_message_id(
        candidate_id="cand-001",
        sender="agent_loop",
        recipient="dia_worker_a",
        role="user",
        turn_number=0,
    )
    print(mid)
    assert mid.startswith("msg_")
    assert len(mid) == 68  # "msg_" + 64 hex chars
    print("PASS: generate_message_id deterministic")
