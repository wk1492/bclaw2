"""
Phase 2A: 14 required tests for the deterministic structured-block extractor.
No ledger writes. No model calls. No network.
"""
from epistemic_extractor import (
    EXTRACTOR_VERSION,
    extract_blocks,
    extract_from_event,
    extract_from_transcript,
    validate_block,
)


def _block(type_="specification", payload=None):
    if payload is None:
        payload = {"k": "v"}
    return {"type": type_, "payload": payload}


def _bclaw_fence(obj_str: str) -> str:
    return f"```bclaw\n{obj_str}\n```"


def _event(content: str, message_id: str = "tmsg_test001") -> dict:
    return {"message_id": message_id, "content": content}


# 1
def test_extract_blocks_empty_string():
    assert extract_blocks("") == []


# 2
def test_extract_blocks_prose_only():
    prose = "The horse faded late. No structured content here. Move along."
    assert extract_blocks(prose) == []


# 3
def test_extract_blocks_single_valid_block():
    content = _bclaw_fence('{"type": "specification", "payload": {"key": "val"}}')
    blocks = extract_blocks(content)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "specification"
    assert blocks[0]["payload"] == {"key": "val"}


# 4
def test_extract_blocks_multiple_blocks():
    b1 = _bclaw_fence('{"type": "constraint", "payload": {"n": 1}}')
    b2 = _bclaw_fence('{"type": "computation", "payload": {"op": "sum"}}')
    content = f"Prose before.\n{b1}\nMiddle prose.\n{b2}\nProse after."
    blocks = extract_blocks(content)
    assert len(blocks) == 2
    assert blocks[0]["type"] == "constraint"
    assert blocks[1]["type"] == "computation"


# 5
def test_extract_blocks_malformed_json_produces_error_entry():
    content = _bclaw_fence("{not valid json")
    blocks = extract_blocks(content)
    assert len(blocks) == 1
    assert "_error" in blocks[0]
    assert "_raw" in blocks[0]


# 6
def test_validate_block_valid_passes():
    result = validate_block(_block())
    assert result["ok"] is True
    assert result["block"] == _block()


# 7
def test_validate_block_missing_type_fails():
    result = validate_block({"payload": {"x": 1}})
    assert result["ok"] is False
    assert "type" in result["error"]


# 8
def test_validate_block_missing_payload_fails():
    result = validate_block({"type": "specification"})
    assert result["ok"] is False
    assert "payload" in result["error"]


# 9
def test_validate_block_payload_not_dict_fails():
    result = validate_block({"type": "specification", "payload": ["list", "not", "dict"]})
    assert result["ok"] is False
    assert "payload" in result["error"]


# 10
def test_extract_from_event_no_blocks_ok():
    event = _event("This is pure prose. No blocks embedded.")
    result = extract_from_event(event)
    assert result["ok"] is True
    assert result["blocks"] == []
    assert result["validated"] == []
    assert result["message_id"] == "tmsg_test001"


# 11
def test_extract_from_event_with_valid_block():
    fence = _bclaw_fence('{"type": "inference", "payload": {"claim": "fast pace"}}')
    event = _event(f"Analysis: {fence}", message_id="tmsg_aaa")
    result = extract_from_event(event)
    assert result["ok"] is True
    assert len(result["blocks"]) == 1
    assert len(result["validated"]) == 1
    assert result["validated"][0]["ok"] is True


# 12
def test_extract_from_transcript_empty_events():
    artifact = extract_from_transcript([])
    assert "artifact_id" in artifact
    assert artifact["block_count"] == 0
    assert artifact["error_count"] == 0
    assert artifact["version"] == EXTRACTOR_VERSION
    assert artifact["results"] == []


# 13
def test_extract_from_transcript_two_events():
    fence = _bclaw_fence('{"type": "specification", "payload": {"step": 1}}')
    e1 = _event(fence, message_id="tmsg_001")
    e2 = _event(fence, message_id="tmsg_002")
    artifact = extract_from_transcript([e1, e2])
    assert artifact["block_count"] == 2
    assert artifact["error_count"] == 0
    assert len(artifact["results"]) == 2


# 14
def test_artifact_id_is_deterministic():
    fence = _bclaw_fence('{"type": "constraint", "payload": {"limit": 42}}')
    events = [_event(fence, message_id="tmsg_x")]
    id1 = extract_from_transcript(events)["artifact_id"]
    id2 = extract_from_transcript(events)["artifact_id"]
    assert id1 == id2
    # changes when input changes
    events_alt = [_event("no blocks", message_id="tmsg_x")]
    id3 = extract_from_transcript(events_alt)["artifact_id"]
    assert id1 != id3
