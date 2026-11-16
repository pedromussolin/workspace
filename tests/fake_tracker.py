"""An in-memory tracker for the tests that need the port and not a Jira server."""

from datetime import date

from ws.taskmodel import Status
from ws.tracker import write
from ws.tracker.errors import TrackerError
from ws.tracker.jira_adapter import JIRA_CAPABILITIES
from ws.tracker.port import CAPABILITIES, Card, CardQuery

NEEDS = {
    "sprint": "sprint",
    "start": "start_date",
    "type": "change_type",
    "reporter": "set_reporter",
    "epic": "epic_parent",
    "body": "description",
}
FIELDS = {"epic": "parent"}
OPS_NEEDING = {"worklog": "worklog", "link": "link_types"}
CURRENT = ("title", "priority", "assignee", "reporter", "parent", "due", "sprint", "start", "type")


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


class _BodyRefused(ValueError):
    def __init__(self, message: str, line: int):
        super().__init__(f"line {line}: {message}")
        self.line = line


class FakeTracker:
    """Reads cards from a dict. With `kind="memory"` it also is a `Writer`: it plans the drafts
    into `SET`/`POST` calls over `cards/...` and applies them to its own records."""

    kind = "jira"
    name = "Memória"
    target = "memory://cards"

    def __init__(
        self,
        cards=(),
        *,
        account="acc-me",
        capabilities=None,
        names=None,
        today=date(2026, 11, 16),
        descriptions=None,
        kind="jira",
    ):
        self.kind = kind
        default = CAPABILITIES if kind == "memory" else JIRA_CAPABILITIES
        self.capabilities = frozenset(default if capabilities is None else capabilities)
        self._cards = {item.ref: item for item in cards}
        self._account = account
        self._names = names or {}
        self._today = today
        self._descriptions = descriptions or {}
        self.reads: list[str] = []
        self.records: dict[str, dict] = {}
        self.sent: list[dict] = []

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

    def plan(self, entries: list[dict]) -> dict:
        taken = set(self._cards) | set(self.records)
        steps = []
        for entry in entries:
            step = self._step(entry, taken)
            if step["card"] and step["op"] == "create":
                taken.add(step["card"])
            steps.append(step)
        return {
            "$schema": "card-plan",
            "version": 1,
            "tracker": "memory",
            "target": self.target,
            "today": self._today.isoformat(),
            "steps": steps,
        }

    def _step(self, entry: dict, taken: set[str]) -> dict:
        document = entry["write"]
        step = {
            "draft": entry["source"],
            "op": document["op"] if document else "create",
            "card": None,
            "title": None,
            "preview": [],
            "warnings": [],
            "problems": list(entry["problems"]),
            "before": {},
            "native": [],
        }
        if document is None:
            return step
        draft = write.from_document(document)
        step["card"] = draft.values.get("key")
        if draft.op == "create":
            step["title"] = draft.title
            step["card"] = f"TS-{max([199, *(int(key[3:]) for key in taken)]) + 1}"
            step["problems"] += self._lacking(draft)
            body = {"key": step["card"], "title": draft.title}
            body.update(self._json(draft.values))
            if draft.body.strip():
                body["description"] = draft.body
            step["native"] = [{"method": "POST", "path": "cards", "body": body}]
            step["preview"] = [f"Criar {step['card']}: {draft.title}"]
        elif (current := self._cards.get(step["card"])) is None:
            step["problems"].append(f"card {step['card']} not found")
        else:
            step["problems"] += self._lacking(draft)
            self._edit(step, draft, current)
        if not step["problems"]:
            return step
        step["native"] = []
        return step

    def _lacking(self, draft) -> list[str]:
        needed = {OPS_NEEDING[draft.op]} if draft.op in OPS_NEEDING else set()
        described = draft.op in ("create", "edit") and draft.body.strip()
        used = [*draft.values, *(["body"] if described else [])]
        needed |= {NEEDS[name] for name in used if name in NEEDS}
        return [f"the memory tracker lacks {name}" for name in sorted(needed - self.capabilities)]

    @staticmethod
    def _json(values: dict) -> dict:
        return {
            name: value.isoformat() if isinstance(value, date) else value
            for name, value in values.items()
            if name != "key"
        }

    def _edit(self, step: dict, draft, current: Card) -> None:
        path = f"cards/{step['card']}"
        values = self._json(draft.values)
        if draft.op == "edit":
            changed = {}
            for name, value in values.items():
                held = getattr(current, FIELDS.get(name, name), None)
                held = held.isoformat() if isinstance(held, date) else held
                if held != value:
                    changed[FIELDS.get(name, name)] = value
                    step["before"][FIELDS.get(name, name)] = held
            if draft.body.strip():
                changed["description"] = draft.body
            if not changed:
                step["problems"].append("nothing to change")
                return
            step["native"] = [{"method": "SET", "path": path, "body": changed}]
            step["preview"] = [f"{name}: {value}" for name, value in changed.items()]
        elif draft.op == "move":
            step["native"] = [{"method": "SET", "path": path, "body": {"status": values["to"]}}]
            step["preview"] = [f"Mover para {values['to']}"]
        elif draft.op == "comment":
            body = {"body": draft.body}
            step["native"] = [{"method": "POST", "path": f"{path}/comments", "body": body}]
            step["preview"] = ["Comentar"]
        elif draft.op == "worklog":
            body = {**values, "body": draft.body}
            step["native"] = [{"method": "POST", "path": f"{path}/worklogs", "body": body}]
            step["preview"] = [f"Lançar {values['time']}"]
        else:
            kinds = [kind for kind in ("blocks", "blocked_by", "relates") if kind in values]
            step["native"] = [
                {"method": "POST", "path": f"{path}/links", "body": {"kind": kind, "to": other}}
                for kind in kinds
                for other in values[kind]
            ]
            step["preview"] = [f"Vincular {kind}" for kind in kinds]

    def guard(self, calls: list[dict]) -> str | None:
        for call in calls:
            allowed = call["method"] in ("SET", "POST") and call["path"].split("/")[0] == "cards"
            if not allowed:
                return f"{call['method']} {call['path']}"
        return None

    def _known(self, key: str) -> dict:
        """The record of a card that exists; a card that does not is a 404, as in a real tracker."""
        if key not in self._cards and key not in self.records:
            raise TrackerError(f"card {key} not found", status=404)
        return self.records.setdefault(key, {})

    def send(self, call: dict) -> object:
        parts = call["path"].split("/")
        if call["method"] == "POST" and parts == ["cards"]:
            key = call["body"]["key"]
            self.records[key] = dict(call["body"])
            reply: dict = {"key": key}
        elif call["method"] == "SET" and len(parts) == 2:
            self._known(parts[1]).update(call["body"])
            reply = {}
        elif (
            call["method"] == "POST"
            and len(parts) == 3
            and parts[2]
            in (
                "comments",
                "worklogs",
                "links",
            )
        ):
            self._known(parts[1]).setdefault(parts[2], []).append(call["body"])
            reply = {}
        else:
            raise TrackerError(f"the memory tracker refuses {call['method']} {call['path']}")
        self.sent.append(call)
        return reply

    def apply(self, plan: dict, send=None):
        return write.apply_steps(self, plan, send or self.send)

    def created_key(self, reply: object) -> str | None:
        return reply.get("key") if isinstance(reply, dict) else None

    def find_hint(self, title: str) -> str:
        return f"procure nos cards em memória pelo título {title!r}"

    def render_body(self, markdown: str) -> str:
        for number, line in enumerate(markdown.splitlines(), 1):
            if "\x00" in line:
                raise _BodyRefused("a NUL character cannot be held", number)
        return markdown

    def card_url(self, key: str) -> str:
        return f"memory://{key}"


INSTALLED: list[FakeTracker] = []


def open_writer(config, entries):
    return INSTALLED[0]


def open_tracker(config):
    return INSTALLED[0]
