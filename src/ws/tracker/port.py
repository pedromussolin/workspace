"""The tracker port: what the core reads from a tracker, whatever the tracker is.

The port only reads cards and reports what the tracker can do; every write goes through the
`ws card` drafts. People are tracker account ids here; the dev ids of the repo are mapped by
`People`.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

from ws.taskmodel import Status
from ws.userconfig import Person, UserConfig

CAPABILITIES = (
    "worklog",
    "sprint",
    "start_date",
    "initiative",
    "epic_parent",
    "set_reporter",
    "change_type",
    "link_types",
)


class TrackerSetup(Exception):
    """The tracker is not configured or reachable by configuration (exit 2)."""


class TrackerError(Exception):
    """The tracker answered wrongly or not at all (exit 3)."""


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


@dataclass(frozen=True)
class CardQuery:
    parent_in: tuple[str, ...]
    role: str = "all"
    open_only: bool = True


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

        return cls(config.people, config.tracker_kind, dev_id(config.identity_email), own_account)

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


def open_tracker() -> Tracker:
    from ws import card
    from ws.tracker.jira_adapter import JiraTracker

    try:
        settings, client = card.session({"project", "types"})
    except card.SetupNeeded as error:
        raise TrackerSetup(str(error)) from None
    return JiraTracker(client, settings)
