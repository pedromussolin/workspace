"""An in-memory tracker for the tests that need the port and not a Jira server."""

from datetime import date

from ws.taskmodel import Status
from ws.tracker.jira_adapter import JIRA_CAPABILITIES
from ws.tracker.port import Card, CardQuery


def make_card(ref: str, **fields) -> Card:
    values = {
        "title": f"[FRONT] {ref}",
        "type": "task",
        "level": 0,
        "parent": "TS-100",
        "assignee": "acc-me",
        "reporter": "acc-me",
        "status": Status.TODO,
        "due": None,
        "priority": "Medium",
        "sprint": None,
        "start": None,
    }
    values.update(fields)
    return Card(ref=ref, **values)


class FakeTracker:
    kind = "jira"

    def __init__(
        self,
        cards=(),
        *,
        account="acc-me",
        capabilities=None,
        names=None,
        today=date(2026, 11, 16),
        descriptions=None,
    ):
        self.capabilities = frozenset(JIRA_CAPABILITIES if capabilities is None else capabilities)
        self._cards = {item.ref: item for item in cards}
        self._account = account
        self._names = names or {}
        self._today = today
        self._descriptions = descriptions or {}
        self.reads: list[str] = []

    def me(self) -> str:
        return self._account

    def today(self) -> date:
        return self._today

    def card(self, ref: str) -> Card | None:
        self.reads.append(ref)
        return self._cards.get(ref)

    def cards(self, query: CardQuery) -> list[Card]:
        found = []
        for item in self._cards.values():
            mine = item.assignee == self._account
            asked = item.reporter == self._account
            wanted = {
                "mine": mine,
                "following": asked and not mine,
                "all": mine or asked,
            }[query.role]
            if item.parent not in query.parent_in or not wanted:
                continue
            if query.open_only and item.status in (Status.DONE, Status.CANCELLED):
                continue
            found.append(item)
        return found

    def display_name(self, account: str) -> str:
        return self._names.get(account, account)

    def description(self, ref: str) -> str | None:
        return self._descriptions.get(ref) or None
