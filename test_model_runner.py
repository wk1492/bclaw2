import copy
import hashlib
import json

import pytest

from model_runner import run_proposal
from transcript_event import canonical_json

RUN_ID = "run_test_001"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# 1. Returns all required keys and no extras
def test_returns_required_keys():
    result = run_proposal(RUN_ID, "agent_a", "agent_b", "proposal", "test prompt")
    expected = {"run_id", "sender", "recipient", "role", "model_name",
                "prompt_hash", "content", "output_hash"}
    assert set(result.keys()) == expected


# 2. Repeated calls with same inputs return byte-identical canonical JSON
def test_repeated_calls_byte_identical():
    kwargs = dict(run_id=RUN_ID, sender="a", recipient="b", role="proposal", prompt="p")
    assert canonical_json(run_proposal(**kwargs)) == canonical_json(run_proposal(**kwargs))


# 3. Output is JSON-safe
def test_output_is_json_safe():
    result = run_proposal(RUN_ID, "a", "b", "proposal", "hello")
    roundtripped = json.loads(json.dumps(result, sort_keys=True))
    assert roundtripped == result


# 4. deepcopy invariance — deepcopy equals original
def test_deepcopy_invariance():
    result = run_proposal(RUN_ID, "a", "b", "critique", "deep copy test")
    assert copy.deepcopy(result) == result


# 5. canonical_json is stable across two independent calls
def test_canonical_json_stable():
    kwargs = dict(run_id=RUN_ID, sender="s", recipient="r", role="reply", prompt="stable?")
    assert canonical_json(run_proposal(**kwargs)) == canonical_json(run_proposal(**kwargs))


# 6. No timestamp or ledger-decoration fields in result
def test_no_nondeterministic_fields():
    result = run_proposal(RUN_ID, "a", "b", "proposal", "check fields")
    banned = {"timestamp", "created_at", "event_id", "message_id",
              "event_hash", "rolling_hash", "previous_hash"}
    assert banned.isdisjoint(result.keys()), f"banned fields present: {banned & result.keys()}"


# 7. No float values anywhere in result
def test_no_float_values():
    result = run_proposal(RUN_ID, "a", "b", "proposal", "no floats")
    for k, v in result.items():
        assert not isinstance(v, float), f"field {k!r} is a float"


# 8. Invalid role raises ValueError
def test_invalid_role_raises():
    with pytest.raises(ValueError, match="role"):
        run_proposal(RUN_ID, "a", "b", "invalid_role", "test")


# 9. Empty run_id raises ValueError
def test_empty_run_id_raises():
    with pytest.raises(ValueError, match="run_id"):
        run_proposal("", "a", "b", "proposal", "test")


# 10. prompt_hash is sha256 of prompt
def test_prompt_hash_is_sha256_of_prompt():
    prompt = "deterministic prompt"
    result = run_proposal(RUN_ID, "a", "b", "proposal", prompt)
    assert result["prompt_hash"] == _sha256(prompt)


# 11. output_hash is sha256 of content
def test_output_hash_is_sha256_of_content():
    result = run_proposal(RUN_ID, "a", "b", "proposal", "check output hash")
    assert result["output_hash"] == _sha256(result["content"])


# 12. Runner is a pure function — no files created in tmp_path
def test_no_file_io(tmp_path):
    before = set(tmp_path.iterdir())
    run_proposal(RUN_ID, "a", "b", "proposal", "no io test")
    assert set(tmp_path.iterdir()) == before


# 13. content is a non-empty str
def test_content_is_nonempty_str():
    result = run_proposal(RUN_ID, "a", "b", "arbiter", "content check")
    assert isinstance(result["content"], str) and len(result["content"]) > 0


# 14. All result values are str
def test_all_values_are_str():
    result = run_proposal(RUN_ID, "a", "b", "system", "type check")
    for k, v in result.items():
        assert isinstance(v, str), f"field {k!r} is {type(v).__name__}, expected str"


# 15. Input fields are echoed verbatim in result
def test_input_fields_echoed():
    result = run_proposal("run_xyz", "sender_s", "recipient_r", "critique",
                          "echo test", model_name="stub")
    assert result["run_id"] == "run_xyz"
    assert result["sender"] == "sender_s"
    assert result["recipient"] == "recipient_r"
    assert result["role"] == "critique"
    assert result["model_name"] == "stub"


# 16. All valid roles are accepted
def test_all_valid_roles_accepted():
    for role in ("proposal", "critique", "reply", "arbiter", "system"):
        result = run_proposal(RUN_ID, "a", "b", role, f"test {role}")
        assert result["role"] == role
