import copy
import hashlib
import json

from transcript_event import VALID_ROLES, canonical_json

# Exhaustive allowlist — any field not in this set is rejected.
_ALLOWED_FIELDS = frozenset({
    "run_id", "sender", "recipient", "role",
    "model_name", "prompt_hash", "content", "output_hash",
})


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stub_content(model_name: str, prompt_hash: str) -> str:
    return f"[STUB:{model_name}] prompt_hash={prompt_hash[:12]}"


def _validate_input(run_id, sender, recipient, role, prompt, model_name):
    for name, val in [
        ("run_id", run_id), ("sender", sender), ("recipient", recipient),
        ("role", role), ("prompt", prompt), ("model_name", model_name),
    ]:
        if not isinstance(val, str) or not val:
            raise ValueError(f"runner input {name!r} must be a non-empty str")
    if role not in VALID_ROLES:
        raise ValueError(f"role {role!r} not in VALID_ROLES {sorted(VALID_ROLES)}")


def _validate_payload(payload: dict) -> None:
    extra = set(payload.keys()) - _ALLOWED_FIELDS
    if extra:
        raise ValueError(f"runner payload contains forbidden fields: {sorted(extra)}")
    missing = _ALLOWED_FIELDS - set(payload.keys())
    if missing:
        raise ValueError(f"runner payload missing required fields: {sorted(missing)}")
    for k, v in payload.items():
        if not isinstance(v, str):
            raise TypeError(f"runner payload field {k!r} must be str, got {type(v).__name__}")
    try:
        json.loads(canonical_json(payload))
    except Exception as exc:
        raise ValueError(f"runner payload is not JSON-safe: {exc}") from exc
    if copy.deepcopy(payload) != payload:
        raise ValueError("runner payload fails deepcopy invariance")


def run_proposal(
    run_id: str,
    sender: str,
    recipient: str,
    role: str,
    prompt: str,
    model_name: str = "stub",
) -> dict:
    """
    Return a pure, deterministic proposal payload. Never writes to disk or network.
    Caller constructs transcript events from the returned payload.
    """
    _validate_input(run_id, sender, recipient, role, prompt, model_name)
    prompt_hash = _sha256(prompt)
    content = _stub_content(model_name, prompt_hash)
    output_hash = _sha256(content)
    payload = {
        "run_id": run_id,
        "sender": sender,
        "recipient": recipient,
        "role": role,
        "model_name": model_name,
        "prompt_hash": prompt_hash,
        "content": content,
        "output_hash": output_hash,
    }
    _validate_payload(payload)
    return payload
