from message_bus import get_outbox
from real_dia_worker import DiAWorker


def run_workers_once(worker_configs: list) -> dict:
    """
    Run each worker exactly once in deterministic order (sorted by worker_id).
    Returns counts and collected replies.
    """
    ordered = sorted(worker_configs, key=lambda w: w["worker_id"])
    all_replies = []
    worker_reply_counts = {}

    for cfg in ordered:
        worker = DiAWorker(
            worker_id=cfg["worker_id"],
            model_name=cfg.get("model_name", "stub"),
            backend=cfg.get("backend", "stub"),
            max_context=cfg.get("max_context", 10),
        )
        replies = worker.run()
        worker_reply_counts[cfg["worker_id"]] = len(replies)
        all_replies.extend(replies)

    return {
        "worker_count": len(ordered),
        "reply_count": len(all_replies),
        "worker_reply_counts": worker_reply_counts,
        "replies": all_replies,
    }


def collect_outbox_replies(worker_ids: list) -> list:
    """Collect all outbox replies from the listed workers in deterministic order."""
    replies = []
    for wid in sorted(worker_ids):
        replies.extend(get_outbox(wid))
    return replies
