"""
tests/fixtures/transcript_graphs.py

Canonical transcript graph fixtures for fingerprint tests.
All events are data-only dicts. No ledger I/O. No model calls.
"""
T = "transcript.message"


def _e(mid, parent=None):
    ev = {"event_type": T, "message_id": mid}
    if parent:
        ev["parent_message_id"] = parent
    return ev


def linear_chain():
    """root → child → grandchild"""
    return [_e("tmsg_root"), _e("tmsg_child", parent="tmsg_root"), _e("tmsg_grand", parent="tmsg_child")]


def branching_critique():
    """root → {tmsg_a, tmsg_b}; tmsg_a → tmsg_c"""
    return [_e("tmsg_a"), _e("tmsg_b", parent="tmsg_a"), _e("tmsg_c", parent="tmsg_a"), _e("tmsg_d", parent="tmsg_b")]


def orphan_graph():
    """tmsg_root (true root) + tmsg_orphan (parent absent from set)"""
    return [_e("tmsg_root"), _e("tmsg_orphan", parent="tmsg_ghost")]


def unicode_graph():
    """Graph with Unicode message_ids and parent_ids."""
    return [
        {"event_type": T, "message_id": "tmsg_中文"},
        {"event_type": T, "message_id": "tmsg_élève", "parent_message_id": "tmsg_中文"},
    ]


# Stable expected hashes (computed from current algorithm; act as regression guards)
EXPECTED_HASHES = {
    "linear_chain":       "e372cde693f5625272627f57e13d368ba9aeecc8a3b472d75f22b38e53243d7b",
    "branching_critique": "0299d56f269c2c86ff9fc3cd543273a4c77ace6a5108f54be78cd8e89a8b436b",
    "orphan_graph":       "63ce393f5ae3be02c473111c7c9ce4980cc1ce69b056fe941c23f93cbba3e86a",
}
