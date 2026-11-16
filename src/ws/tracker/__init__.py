"""Neutral tracker layer: the vocabulary every skill and the core use, and the adapter check.

Only the Jira adapter exists; its engine lives in `ws.card`, `ws.cardrules` and `ws.jira`.
"""

ADAPTERS = {"jira": "ws.tracker.jira_adapter"}
KNOWN_KINDS = tuple(ADAPTERS)


class UnknownTracker(Exception):
    pass


def require_kind(kind: str) -> None:
    if kind not in ADAPTERS:
        raise UnknownTracker(f"tracker {kind!r} has no adapter yet; known: {', '.join(ADAPTERS)}")
