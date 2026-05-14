import hashlib

from transcript_event import canonical_json, make_transcript_event

EPISTEMIC_FIELDS = {"claim_type", "evidence_refs", "confidence", "epistemic_status"}

VALID_CLAIM_TYPES = {"assertion", "hypothesis", "observation", "inference", "retraction"}
VALID_EPISTEMIC_STATUSES = {"proposed", "supported", "contested", "refuted", "synthesized"}


def make_epistemic_event(
    run_id, sender, recipient, role, content, created_at,
    references=None, parent_message_id=None, metadata=None,
    claim_type=None, evidence_refs=None, confidence=None, epistemic_status=None,
):
    event = make_transcript_event(
        run_id=run_id, sender=sender, recipient=recipient,
        role=role, content=content, created_at=created_at,
        references=references, parent_message_id=parent_message_id,
        metadata=metadata,
    )
    if claim_type is not None:
        if claim_type not in VALID_CLAIM_TYPES:
            raise ValueError(
                f"claim_type {claim_type!r} not in VALID_CLAIM_TYPES {sorted(VALID_CLAIM_TYPES)}"
            )
        event["claim_type"] = claim_type
    if evidence_refs is not None:
        if not isinstance(evidence_refs, list):
            raise ValueError("evidence_refs must be a list")
        event["evidence_refs"] = evidence_refs
    if confidence is not None:
        if not isinstance(confidence, float) or not (0.0 <= confidence <= 1.0):
            raise ValueError(
                f"confidence must be a float in [0.0, 1.0], got {confidence!r}"
            )
        event["confidence"] = confidence
    if epistemic_status is not None:
        if epistemic_status not in VALID_EPISTEMIC_STATUSES:
            raise ValueError(
                f"epistemic_status {epistemic_status!r} not in VALID_EPISTEMIC_STATUSES"
                f" {sorted(VALID_EPISTEMIC_STATUSES)}"
            )
        event["epistemic_status"] = epistemic_status
    return event


def epistemic_claim_id(event: dict) -> str:
    return "claim_" + hashlib.sha256(
        canonical_json(event).encode("utf-8")
    ).hexdigest()[:24]


def strip_epistemic_fields(event: dict) -> dict:
    return {k: v for k, v in event.items() if k not in EPISTEMIC_FIELDS}
