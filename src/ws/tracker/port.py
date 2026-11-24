"""The tracker port: what the core reads from a tracker, whatever the tracker is.

`Tracker` reads cards and reports what the tracker can do; `Writer` plans and sends the `ws card`
drafts, the only way a write reaches a tracker. People are tracker account ids here; the dev ids
of the repo are mapped by `People`.
"""

import importlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date
from types import ModuleType
from typing import Protocol, runtime_checkable

from ws import userconfig
from ws.taskmodel import Status
from ws.tracker import ADAPTERS, UnknownTracker, require_kind
from ws.tracker.errors import TrackerError, TrackerSetup
from ws.userconfig import Person, UserConfig

__all__ = [
    "CAPABILITIES",
    "Card",
    "CardQuery",
    "Link",
    "People",
    "Tracker",
    "TrackerError",
    "TrackerSetup",
    "Worklog",
    "Writer",
    "open_tracker",
    "open_writer",
]

CAPABILITIES = (
    "worklog",
    "sprint",
    "start_date",
    "initiative",
    "epic_parent",
    "set_reporter",
    "change_type",
    "link_types",
    "description",
)


@dataclass(frozen=True)
class Link:
    kind: str
    ref: str


@dataclass(frozen=True)
class Card:
    ref: str
    title: str
    type: str | None
    level: int
    parent: str | None
    assignee: str | None
    reporter: str | None
    status: Status
    due: date | None
    priority: str | None
    sprint: str | None
    links: tuple[Link, ...] = ()
    start: date | None = None
    labels: tuple[str, ...] = ()
    estimate_minutes: int | None = None
    spent_minutes: int | None = None
    created: date | None = None


@dataclass(frozen=True)
class Worklog:
    """Time logged on a card: the day it was logged for, in minutes, by a tracker account."""

    day: date
    minutes: int
    author: str


@dataclass(frozen=True)
class CardQuery:
    """`sprint` is "active" (the board's open sprint), "next" (its earliest future sprint) or the
    exact name of a sprint; `assignees` are tracker account ids and, when given, say whose cards
    are asked for instead of `role`. With `parent_in` empty, the other fields alone select the
    cards; with none set, no card."""

    parent_in: tuple[str, ...] = ()
    role: str = "all"
    open_only: bool = True
    sprint: str | None = None
    assignees: tuple[str, ...] = ()


@runtime_checkable
class Tracker(Protocol):
    kind: str
    capabilities: frozenset[str]

    def me(self) -> str: ...

    def today(self) -> date:
        """Today in the time zone of the user's tracker account."""
        ...

    def card(self, ref: str) -> Card | None:
        """None: the card is absent from the configured project."""
        ...

    def cards(self, query: CardQuery) -> list[Card]: ...

    def display_name(self, account: str) -> str: ...

    def description(self, ref: str) -> str | None:
        """The card description as plain text, headings as `## `; None when empty or absent."""
        ...

    def worklogs(self, ref: str) -> list[Worklog]:
        """Every worklog of the card, whoever logged it; an absent card has none."""
        ...


class People:
    """The people of `config.toml`, both ways between dev ids and tracker accounts."""

    def __init__(self, people: dict[str, Person], kind: str, own_dev_id: str, own_account: str):
        self._people = people
        self._kind = kind
        self._own_dev_id = own_dev_id
        self._own_account = own_account

    @classmethod
    def from_config(cls, config: UserConfig, own_account: str) -> "People":
        from ws.identity import dev_id

        return cls(
            config.people, config.tracker_kind, dev_id(config.require_identity_email()), own_account
        )

    def account(self, dev_id: str) -> str | None:
        if dev_id == self._own_dev_id:
            return self._own_account
        found = self._people.get(dev_id)
        return found.ids.get(self._kind) or None if found else None

    def dev_id(self, account: str) -> str | None:
        if account == self._own_account:
            return self._own_dev_id
        for dev_id, person in self._people.items():
            if person.ids.get(self._kind) == account:
                return dev_id
        return None

    def problem(self, dev_id: str) -> str | None:
        if dev_id == self._own_dev_id:
            return None
        found = self._people.get(dev_id)
        if found is None:
            return (
                f"unknown person {dev_id!r}: run ws people add <e-mail> and paste the block "
                "into config.toml"
            )
        if not found.ids.get(self._kind):
            return (
                f"person {dev_id!r} has no {self._kind} id; run ws people add <e-mail> and "
                "paste the block into config.toml"
            )
        return None


@runtime_checkable
class Writer(Tracker, Protocol):
    name: str
    target: str

    def plan(self, entries: list[dict]) -> dict: ...

    def guard(self, calls: list) -> str | None: ...

    def send(self, call: object) -> object: ...

    def apply(self, plan: dict, send: Callable | None = None) -> Iterator[dict]: ...

    def created_key(self, reply: object) -> str | None: ...

    def find_hint(self, title: str) -> str: ...

    def render_body(self, markdown: str) -> object:
        """Raises `ValueError` with a `line` attribute for text the tracker cannot hold."""
        ...

    def card_url(self, key: str) -> str: ...


def _adapter() -> tuple[UserConfig, ModuleType]:
    try:
        config = userconfig.load_config()
        require_kind(config.tracker_kind)
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid, UnknownTracker) as error:
        raise TrackerSetup(str(error)) from None
    return config, importlib.import_module(ADAPTERS[config.tracker_kind])


def open_tracker(connection_only: bool = False) -> Tracker:
    """The tracker of the config. `connection_only` asks for the listings and the account
    lookups, which need no more than the connection: each read then checks its own config."""
    config, adapter = _adapter()
    if connection_only:
        return adapter.open_tracker(config, connection_only=True)
    return adapter.open_tracker(config)


def open_writer(entries: list[dict]) -> Writer:
    """The writer of the configured tracker, set up for the `card-write` entries it will plan."""
    config, adapter = _adapter()
    return adapter.open_writer(config, entries)
