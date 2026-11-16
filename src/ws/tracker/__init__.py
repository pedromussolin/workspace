"""Neutral tracker layer: the vocabulary every skill and the core use, and the adapter check.

Only the Jira adapter exists; its engine lives in `ws.card`, `ws.cardrules` and `ws.jira`.
The functions below are the facade: they pick the adapter from `config.tracker_kind`, and no
adapter is imported at module top.
"""

import importlib

ADAPTERS = {"jira": "ws.tracker.jira"}
KNOWN_KINDS = tuple(ADAPTERS)


class UnknownTracker(Exception):
    pass


def require_kind(kind: str) -> None:
    if kind not in ADAPTERS:
        raise UnknownTracker(f"tracker {kind!r} has no adapter yet; known: {', '.join(ADAPTERS)}")


def _adapter(config):
    from ws.tracker.errors import TrackerSetup

    try:
        require_kind(config.tracker_kind)
    except UnknownTracker as error:
        raise TrackerSetup(str(error)) from None
    return importlib.import_module(ADAPTERS[config.tracker_kind])


def _open():
    from ws.tracker import port

    return port.open_tracker(connection_only=True)


def list_tasks(since, role) -> dict:
    return _open().list_tasks(since, role)


def discover_toml() -> str:
    return _open().discover_toml()


def accounts_for(email) -> list[str]:
    return _open().accounts_for(email)


def account_for(email) -> str | None:
    return _open().account_for(email)


def task_from_listing(card, config):
    adapter = _adapter(config)
    return adapter.task_from_listing(card, getattr(config, config.tracker_kind))


def status_overrides(config) -> dict[str, str]:
    _adapter(config)
    return dict(getattr(config, config.tracker_kind).status_overrides)
