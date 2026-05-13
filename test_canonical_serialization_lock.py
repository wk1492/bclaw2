"""
Canonical serialization lock.
Proves all hash-critical paths use sort_keys=True + separators=(",", ":").
Test 5 proves the ExperimentGraph.graph_hash() violation before the fix is applied.
"""
import hashlib
import json

from transcript_event import canonical_json, message_id_hash


# 1. canonical_json emits sorted keys and compact separators (pinned exact form)
def test_canonical_json_sorted_keys_and_compact_separators():
    payload = {"z": 3, "a": 1, "m": "hello"}
    result = canonical_json(payload)
    assert result == '{"a":1,"m":"hello","z":3}'
    assert '": ' not in result
    assert '", ' not in result


# 2. canonical_json repeated calls are byte-identical
def test_canonical_json_byte_stable_across_calls():
    payload = {"sender": "agent_a", "role": "proposal", "x": 42}
    r1 = canonical_json(payload)
    r2 = canonical_json(payload)
    r3 = canonical_json(dict(reversed(list(payload.items()))))
    assert r1 == r2 == r3


# 3. event_hash (ledger) is invariant to dict insertion order
def test_event_hash_invariant_to_insertion_order():
    from state_serializer import canonical_json as state_canonical
    d1 = {"type": "execution", "payload": {"x": 1, "y": 2}, "status": "ok"}
    d2 = {"status": "ok", "payload": {"y": 2, "x": 1}, "type": "execution"}
    assert state_canonical(d1) == state_canonical(d2)
    h1 = hashlib.sha256(state_canonical(d1).encode()).hexdigest()
    h2 = hashlib.sha256(state_canonical(d2).encode()).hexdigest()
    assert h1 == h2


# 4. message_id_hash is invariant to dict insertion order
def test_message_id_hash_invariant_to_insertion_order():
    p1 = {"event_type": "transcript.message", "content": "test", "sender": "a", "run_id": "r1"}
    p2 = {"run_id": "r1", "sender": "a", "content": "test", "event_type": "transcript.message"}
    assert canonical_json(p1) == canonical_json(p2)
    assert message_id_hash(p1) == message_id_hash(p2)


# 5. ExperimentGraph.graph_hash must use compact separators (proves violation before fix)
def test_graph_hash_uses_compact_separators():
    from underperformance_experiment import ExperimentGraph
    summary = {"b": 2, "a": 1, "label": "test"}
    g = ExperimentGraph(summary)
    expected = hashlib.sha256(
        json.dumps(summary, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert g.graph_hash() == expected, (
        "ExperimentGraph.graph_hash must use separators=(',',':'); "
        "without it json.dumps inserts spaces and diverges from canonical form"
    )


# 6. ledger append writes compact one-LF-per-event JSON
def test_ledger_append_output_is_compact_and_lf_delimited(tmp_path):
    from ledger_writer import LedgerWriter
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    writer.append({"type": "a", "value": 1})
    writer.append({"type": "b", "value": 2})
    writer.append({"type": "c", "value": 3})
    raw = path.read_bytes()
    assert raw.count(b"\n") == 3
    assert b"\r" not in raw
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    for line in raw.decode().splitlines():
        assert '": ' not in line
        assert '", ' not in line
        assert isinstance(json.loads(line), dict)
