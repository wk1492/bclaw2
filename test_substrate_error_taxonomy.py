import json
from pathlib import Path

import pytest

from ledger_writer import LedgerWriter
from substrate_contract import substrate_append_transcript_event, substrate_verify_ledger
from substrate_errors import (
    E_DUPLICATE_MESSAGE_ID,
    E_INVALID_JSON,
    E_MISSING_FINAL_NEWLINE,
    E_MISSING_PARENT,
    E_PREVIOUS_HASH_MISMATCH,
    SUBSTRATE_VERSION,
)
from transcript_event import make_transcript_event
from transcript_validator import TranscriptValidationError

FIXTURE_PATH = Path(__file__).parent / "artifacts" / "baselines" / "provenance_fixtures.json"
CONTRACT_MD = Path(__file__).parent / "SUBSTRATE_CONTRACT.md"

RUN_ID = "run_taxonomy_test"
TS_A = "2026-05-13T10:00:00+00:00"
TS_B = "2026-05-13T10:00:01+00:00"


# 1. SUBSTRATE_VERSION == 1
def test_substrate_version():
    assert SUBSTRATE_VERSION == 1


# 2. SUBSTRATE_CONTRACT.md mentions required terms
def test_contract_doc_mentions_required_terms():
    text = CONTRACT_MD.read_text()
    for term in ["version", "canonical JSON", "sha256", "JSONL", "final LF",
                 "append-only", "read-only"]:
        assert term in text, f"SUBSTRATE_CONTRACT.md missing: {term!r}"


# 3. Every error code appears in SUBSTRATE_CONTRACT.md
def test_all_error_codes_in_contract_doc():
    text = CONTRACT_MD.read_text()
    for code in [E_DUPLICATE_MESSAGE_ID, E_MISSING_PARENT,
                 E_PREVIOUS_HASH_MISMATCH, E_INVALID_JSON, E_MISSING_FINAL_NEWLINE]:
        assert code in text, f"SUBSTRATE_CONTRACT.md missing: {code}"


# 4. duplicate message_id raises same text and .code == E_DUPLICATE_MESSAGE_ID
def test_duplicate_message_id_carries_code(tmp_path):
    path = tmp_path / "ledger.jsonl"
    event = make_transcript_event(RUN_ID, "agent_a", "broadcast", "proposal",
                                  "content", TS_A)
    substrate_append_transcript_event(event, path)
    with pytest.raises(TranscriptValidationError) as exc_info:
        substrate_append_transcript_event(event, path)
    exc = exc_info.value
    assert str(exc).startswith(f"duplicate message_id: {event['message_id']}")
    assert exc.code == E_DUPLICATE_MESSAGE_ID


# 5. missing parent raises same text and .code == E_MISSING_PARENT
def test_missing_parent_carries_code(tmp_path):
    path = tmp_path / "ledger.jsonl"
    event = make_transcript_event(RUN_ID, "agent_a", "broadcast", "proposal",
                                  "content", TS_A)
    orphan = make_transcript_event(RUN_ID, "agent_b", "agent_a", "critique",
                                   "orphan", TS_B,
                                   parent_message_id="tmsg_nonexistent000000000000")
    substrate_append_transcript_event(event, path)
    with pytest.raises(TranscriptValidationError) as exc_info:
        substrate_append_transcript_event(orphan, path)
    exc = exc_info.value
    assert "parent_message_id not in ledger" in str(exc)
    assert exc.code == E_MISSING_PARENT


# 6. previous_hash mismatch: same failure text, adds E_PREVIOUS_HASH_MISMATCH
def test_previous_hash_mismatch_code(tmp_path):
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    writer.append({"type": "a"})
    writer.append({"type": "b"})

    lines = path.read_text().splitlines()
    second = json.loads(lines[1])
    second["previous_hash"] = "0" * 64
    path.write_text(
        lines[0] + "\n" +
        json.dumps(second, sort_keys=True, separators=(",", ":")) + "\n"
    )

    result = substrate_verify_ledger(path)
    assert result["ok"] is False
    assert any("previous_hash mismatch" in f for f in result["failures"])
    assert E_PREVIOUS_HASH_MISMATCH in result["error_codes"]


# 7. invalid JSON: same failure text, adds E_INVALID_JSON
def test_invalid_json_code(tmp_path):
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    writer.append({"type": "a"})
    path.write_bytes(path.read_bytes() + b'{"truncated\n')

    result = substrate_verify_ledger(path)
    assert result["ok"] is False
    assert any("invalid JSON" in f for f in result["failures"])
    assert E_INVALID_JSON in result["error_codes"]


# 8. missing final newline: same failure text, adds E_MISSING_FINAL_NEWLINE
def test_missing_final_newline_code(tmp_path):
    path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path)
    writer.append({"type": "a"})
    path.write_bytes(path.read_bytes().rstrip(b"\n"))

    result = substrate_verify_ledger(path)
    assert result["ok"] is False
    assert any("missing final newline terminator" in f for f in result["failures"])
    assert E_MISSING_FINAL_NEWLINE in result["error_codes"]


# 9. provenance_fixtures.json is unchanged
def test_provenance_fixtures_unchanged():
    fixture = json.loads(FIXTURE_PATH.read_text())
    cases = fixture["cases"]
    assert cases["clean_chain"]["topology_hash"] == \
        "0b0eb7603d3c53b6940c1bef59bbf9fe845a0ce50faf8866d94311a79ecedfb8"
    assert cases["orphaned_critique"]["topology_hash"] == \
        "de676a53f5092e20546c997683d04620d9fe03b5b993bd50736131477acab25d"
    assert cases["broken_references"]["topology_hash"] == \
        "8365b304f600c4b82928bc26bd1dda9a6dacf38f9f0b2805b35b7ba85e6b677f"
    assert cases["clean_chain"]["orphaned"] == []
    assert "tmsg_f634cbe4327975cd9f623d82" in cases["orphaned_critique"]["orphaned"]
    assert "tmsg_missingref0000000000000" in cases["broken_references"]["missing_references"]
