import hashlib
import json
import os
import tempfile
from pathlib import Path

from transcript_event import make_transcript_event
from transcript_ledger import (
    append_transcript_event,
    replay_transcript_events,
    replay_transcript_topology,
    verify_mixed_ledger,
)

RUN_ID = "bclaw4_chaos_001"

_TS = {i: f"2026-05-15T10:{i:02d}:00+00:00" for i in range(1, 11)}

_MOVE_SPECS = [
    {
        "move_id": "m01",
        "role": "proposal",
        "sender": "bclaw4_runner",
        "recipient": "broadcast",
        "goal": "establish_causal_baseline",
        "proposed_action": "assert_causal_edge(fatigue->error_rate,weight=0.7)",
        "allowed_files": ["mesh.db"],
        "drift_check": "schema_invariant",
        "rollback_point": True,
        "parent": None,
        "references_from": [],
    },
    {
        "move_id": "m02",
        "role": "reply",
        "sender": "bclaw4_runner",
        "recipient": "broadcast",
        "goal": "extend_baseline_with_evidence",
        "proposed_action": "cite_evidence(source=track_condition_report,weight=0.6)",
        "allowed_files": [],
        "drift_check": "reference_integrity",
        "rollback_point": False,
        "parent": 0,
        "references_from": [],
    },
    {
        "move_id": "m03",
        "role": "reply",
        "sender": "bclaw4_runner",
        "recipient": "broadcast",
        "goal": "add_corroborating_source",
        "proposed_action": "cite_evidence(source=rapsodo_data,weight=0.65)",
        "allowed_files": [],
        "drift_check": "reference_integrity",
        "rollback_point": False,
        "parent": 1,
        "references_from": [],
    },
    {
        "move_id": "m04",
        "role": "reply",
        "sender": "bclaw4_runner",
        "recipient": "broadcast",
        "goal": "finalize_evidence_chain",
        "proposed_action": "close_evidence_chain(sources=[track_condition_report,rapsodo_data])",
        "allowed_files": [],
        "drift_check": "reference_integrity",
        "rollback_point": False,
        "parent": 2,
        "references_from": [],
    },
    {
        "move_id": "m05",
        "role": "critique",
        "sender": "bclaw4_critic",
        "recipient": "bclaw4_runner",
        "goal": "challenge_evidence_weight",
        "proposed_action": "assert_weight_lower_bound(source=track_condition_report,max=0.4)",
        "allowed_files": [],
        "drift_check": "reference_integrity",
        "rollback_point": True,
        "parent": 0,
        "references_from": [3],
    },
    {
        "move_id": "m06",
        "role": "arbiter",
        "sender": "bclaw4_arbiter",
        "recipient": "broadcast",
        "goal": "resolve_evidence_dispute",
        "proposed_action": "accept_weight(rapsodo_data,0.65);defer_track_condition_report",
        "allowed_files": [],
        "drift_check": "topology_invariant",
        "rollback_point": True,
        "parent": None,
        "references_from": [0, 1, 2, 3, 4],
    },
    {
        "move_id": "m07",
        "role": "proposal",
        "sender": "bclaw4_runner",
        "recipient": "broadcast",
        "goal": "extend_causal_graph",
        "proposed_action": "assert_causal_edge(rapsodo_data->fatigue,weight=0.5)",
        "allowed_files": ["mesh.db"],
        "drift_check": "schema_invariant",
        "rollback_point": False,
        "parent": 5,
        "references_from": [],
    },
    {
        "move_id": "m08",
        "role": "critique",
        "sender": "bclaw4_critic",
        "recipient": "bclaw4_runner",
        "goal": "challenge_new_edge",
        "proposed_action": "assert_missing_confounder(candidate=workload_history)",
        "allowed_files": [],
        "drift_check": "reference_integrity",
        "rollback_point": False,
        "parent": 6,
        "references_from": [],
    },
    {
        "move_id": "m09",
        "role": "reply",
        "sender": "bclaw4_runner",
        "recipient": "bclaw4_critic",
        "goal": "acknowledge_confounder",
        "proposed_action": "add_confounder_note(candidate=workload_history,status=unresolved)",
        "allowed_files": [],
        "drift_check": "reference_integrity",
        "rollback_point": False,
        "parent": 6,
        "references_from": [7],
    },
    {
        "move_id": "m10",
        "role": "arbiter",
        "sender": "bclaw4_arbiter",
        "recipient": "broadcast",
        "goal": "close_experiment",
        "proposed_action": "defer_edge(rapsodo_data->fatigue);record_confounder(workload_history)",
        "allowed_files": [],
        "drift_check": "topology_invariant",
        "rollback_point": True,
        "parent": None,
        "references_from": [5, 6, 7, 8],
    },
]


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_bclaw4_experiment(ledger_path=None) -> dict:
    """
    Execute 10 deterministic ledgered moves against the transcript substrate.
    Returns a summary dict with topology, chain, and replay metadata.
    """
    if ledger_path is None:
        fd, ledger_path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        Path(ledger_path).unlink(missing_ok=True)

    emitted: list[tuple[dict, dict]] = []

    for spec in _MOVE_SPECS:
        move_idx = len(emitted)

        parent_id = None
        if spec["parent"] is not None:
            parent_id = emitted[spec["parent"]][1]["message_id"]

        refs = [emitted[i][1]["message_id"] for i in spec["references_from"]]

        content_payload = {
            "move_id": spec["move_id"],
            "role": spec["role"],
            "sender": spec["sender"],
            "goal": spec["goal"],
            "proposed_action": spec["proposed_action"],
            "allowed_files": spec["allowed_files"],
            "drift_check": spec["drift_check"],
            "rollback_point": spec["rollback_point"],
        }
        content = _canonical(content_payload)

        event = make_transcript_event(
            run_id=RUN_ID,
            sender=spec["sender"],
            recipient=spec["recipient"],
            role=spec["role"],
            content=content,
            created_at=_TS[move_idx + 1],
            parent_message_id=parent_id,
            references=refs,
        )

        append_transcript_event(event, ledger_path)
        emitted.append((spec, event))

    topology = replay_transcript_topology(ledger_path)
    chain = verify_mixed_ledger(ledger_path)
    events = replay_transcript_events(ledger_path)

    summary_body = {
        "run_id": RUN_ID,
        "move_count": len(emitted),
        "move_ids": [s["move_id"] for s, _ in emitted],
        "topology_hash": topology["topology_hash"],
    }
    summary_id = "bclaw4_" + _sha256(_canonical(summary_body))[:24]

    return {
        "summary_id": summary_id,
        "run_id": RUN_ID,
        "ledger_path": str(ledger_path),
        "move_count": len(emitted),
        "move_ids": [s["move_id"] for s, _ in emitted],
        "message_ids": [e["message_id"] for _, e in emitted],
        "topology": topology,
        "chain_ok": chain.get("ok", False),
        "replay_count": len(events),
    }
