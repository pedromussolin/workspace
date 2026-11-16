"""Neutral tracker layer: the vocabulary every skill and the core use, and the adapter check.

Each adapter is a package named in `ADAPTERS` (only `ws.tracker.jira` today). The functions
below are the facade: they pick the adapter from `config.tracker_kind` by that name, and no
adapter is imported at module top.
"""

import importlib

ADAPTERS = {"jira": "ws.tracker.jira"}
KNOWN_KINDS = tuple(ADAPTERS)
ROLES = ("mine", "following", "all")


class UnknownTracker(Exception):
    pass


def require_kind(kind: str | None) -> None:
    if not kind:
        raise UnknownTracker('config.toml: [tracker] kind is not set; add [tracker] kind = "jira"')
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


def card_url_template(config=None) -> str:
    """The link of a task with `{key}` where the key goes; offline, from the config alone."""
    if config is not None:
        return _adapter(config).card_url_template(config.tracker_settings)
    from ws import userconfig
    from ws.tracker.errors import TrackerSetup

    kind, table, path, section = userconfig.load_tracker_table()
    try:
        require_kind(kind)
    except UnknownTracker as error:
        raise TrackerSetup(str(error)) from None
    adapter = importlib.import_module(ADAPTERS[kind])
    try:
        return adapter.card_url_template_from_table(table, path, section)
    except userconfig.ConfigInvalid as error:
        raise TrackerSetup(str(error)) from None


def task_from_listing(card, config):
    return _adapter(config).task_from_listing(card, config.tracker_settings)


def status_overrides(config) -> dict[str, str]:
    _adapter(config)
    return dict(config.tracker_settings.status_overrides)
