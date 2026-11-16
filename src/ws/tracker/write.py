"""The neutral side of a card write: documents, their rules, approval digest, pending record,
apply loop.

Nothing here knows a tracker; an adapter supplies the plan and the `Writer` that sends it.
"""

import hashlib
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date

from ws import approval, contracts
from ws.itemfile import ITEM_PATH
from ws.taskmodel import Status
from ws.tracker.port import TrackerError
from ws.tracker.vocab import ALL_TYPES, CARD_TYPES, LINK_KINDS, UPPER_TYPES

VERSION = 1
SCHEMAS = ("card-write", "card-plan", "card-result")
OPS = ("create", "edit", "move", "comment", "worklog", "link")

REQUIRED = {
    "create": {"type", "priority", "title"},
    "edit": {"key"},
    "move": {"key"},
    "comment": {"key", "body"},
    "worklog": {"key", "time"},
    "link": {"key"},
}
OPTIONAL = {
    "create": {"body", "epic", "parent", "assignee", "reporter", "sprint", "due", "item"},
    "edit": {
        "title",
        "priority",
        "start",
        "due",
        "epic",
        "type",
        "assignee",
        "reporter",
        "parent",
        "sprint",
        "body",
    },
    "move": {"to", "status"},
    "comment": set(),
    "worklog": {"day", "body"},
    "link": {"blocks", "blocked_by", "relates"},
}
HEADER = {"$schema", "version", "op"}
DATES = {"start", "due", "day"}


@dataclass(frozen=True)
class Draft:
    """One card write as `ws card` holds it, from a Markdown draft or a `card-write` document."""

    op: str
    values: dict
    title: str | None
    body: str
    sha256: str


def to_document(draft: Draft) -> dict:
    document: dict = {"$schema": "card-write", "version": VERSION, "op": draft.op}
    for name, value in draft.values.items():
        document[name] = value.isoformat() if isinstance(value, date) else value
    if draft.title is not None:
        document["title"] = draft.title
    if draft.body.strip():
        document["body"] = draft.body
    return document


def from_document(document: dict) -> Draft:
    """The draft of a `card-write` document, its values trimmed as a Markdown draft's are."""
    values = {}
    for name, value in _trimmed(document).items():
        if name == "title" and document["op"] == "create":
            continue
        values[name] = date.fromisoformat(value) if name in DATES else value
    canonical = json.dumps(document, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    title = document.get("title") if document["op"] == "create" else None
    return Draft(
        document["op"],
        values,
        title.strip() if isinstance(title, str) else title,
        document.get("body", ""),
        hashlib.sha256(canonical.encode()).hexdigest(),
    )


def _trimmed(document: dict) -> dict:
    """The values of a document but the header and the body, without surrounding blanks."""
    values = {}
    for name, value in document.items():
        if name in HEADER or name == "body":
            continue
        if isinstance(value, str):
            value = value.strip()
        elif isinstance(value, list):
            value = [item.strip() if isinstance(item, str) else item for item in value]
        values[name] = value
    return values


def check_document(document: dict) -> list[str]:
    name = document.get("$schema")
    if name not in SCHEMAS:
        return [f"$schema: unknown contract {name!r}"]
    if document.get("version") != VERSION:
        return [f"version: unknown version {document.get('version')!r}"]
    problems = contracts.validate(document, name)
    op = document.get("op")
    if name == "card-write" and op in OPS and not problems:
        problems += _op_problems(document, op)
    if name == "card-write" and op in OPS and not problems:
        values = _trimmed(document)
        problems += _value_problems(values) or draft_problems(op, values)
    return problems


def _op_problems(document: dict, op: str) -> list[str]:
    allowed = REQUIRED[op] | OPTIONAL[op] | HEADER
    problems = [f"$.{key}: not a key of op {op}" for key in document if key not in allowed]
    problems += [
        f"$: missing required key {key} for op {op}" for key in sorted(REQUIRED[op] - set(document))
    ]
    for name in sorted(DATES & set(document)):
        if not _is_date(document[name]):
            problems.append(f"$.{name}: expected a date YYYY-MM-DD")
    if "sprint" in document and "sprint" in OPTIONAL[op]:
        problems += _sprint_problems(document["sprint"], op)
    if op == "move":
        problems += _move_rules(document)
    if op == "link" and not any(document.get(kind) for kind in OPTIONAL["link"]):
        problems.append("$: a link needs blocks, blocked_by or relates")
    return problems


def _sprint_problems(sprint: str, op: str) -> list[str]:
    """`sprint` is "active", "next", "backlog" or a sprint's name; the tracker resolves it."""
    if not sprint.strip():
        return ["$.sprint: expected a non-empty string"]
    if op == "create" and sprint == "backlog":
        return ["$.sprint: a create without `sprint` already goes to the backlog"]
    return []


def _is_date(value: object) -> bool:
    try:
        return date.fromisoformat(value).isoformat() == value  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def _value_problems(values: dict) -> list[str]:
    """What the contract's types let through and a Markdown draft refuses, in the same words:
    a blank string, and a list of card keys with a blank or a repeated key."""
    problems = []
    for name in sorted(set(values) - DATES):
        value = values[name]
        if name in LINK_KINDS:
            if not all(value):
                problems.append(f"{name} must be a list of card keys")
            elif problem := repeated_problem(name, value):
                problems.append(problem)
        elif not value:
            problems.append(f"{name} must be a non-empty string")
    return problems


def repeated_problem(name: str, cards: list[str]) -> str | None:
    """The problem of a list of card keys that names a card twice; None when it does not."""
    twice = next((card for card in cards if cards.count(card) > 1), None)
    return None if twice is None else f"{name} lists {twice} twice"


def draft_problems(op: str, values: dict) -> list[str]:
    """The rules every card write follows, whether it came as a Markdown draft or as a
    `card-write` document. `values` are the write's keys but the header, title and body."""
    problems = []
    kind = values.get("type")
    if kind is not None and kind not in ALL_TYPES:
        problems.append(f"type must be one of {', '.join(ALL_TYPES)}")
    elif op == "create":
        problems += _create_rules(kind, values)
    elif op == "edit":
        problems += _edit_rules(kind, values)
    if op == "link":
        problems += _link_rules(values)
    if op == "move":
        problems += _move_rules(values)
    return problems


def _move_rules(values: dict) -> list[str]:
    if "to" in values and "status" in values:
        return ["a move needs exactly one of to or status, not both"]
    if "to" not in values and "status" not in values:
        return ["missing key 'to' for op move"]
    if "status" in values and values["status"] not in {status.value for status in Status}:
        return [f"status must be one of {', '.join(status.value for status in Status)}"]
    return []


def _item_rules(kind: str, values: dict) -> list[str]:
    if "item" not in values:
        return []
    if not ITEM_PATH.fullmatch(values["item"]):
        return ["item must be a path like projects/<slug>/tasks/NN-name.md"]
    if kind not in CARD_TYPES:
        return ["item is only for a card; an epic or an initiative has no item"]
    return []


def _create_rules(kind: str, values: dict) -> list[str]:
    problems = _item_rules(kind, values)
    return problems + _type_rules(kind, values)


def _type_rules(kind: str, values: dict) -> list[str]:
    if kind in CARD_TYPES:
        if "parent" in values:
            return ["parent is only for an epic; a card uses epic"]
        if "epic" not in values:
            return [f"a {kind} needs an epic"]
    elif "epic" in values:
        return ["an epic has no epic; use parent for its initiative"]
    elif kind in UPPER_TYPES and kind != "epic" and "parent" in values:
        return ["an initiative has no parent"]
    return []


def _edit_rules(kind: str | None, values: dict) -> list[str]:
    problems = []
    if kind in UPPER_TYPES:
        problems.append(
            f"type {kind} is not a card type: changing a card's level is done by hand in the "
            "tracker"
        )
    if "epic" in values and "parent" in values:
        problems.append("use epic for a card or parent for an epic, not both")
    return problems


def _link_rules(values: dict) -> list[str]:
    lists = {name: values[name] for name in LINK_KINDS if values.get(name)}
    if not lists:
        return ["a link needs blocks, blocked_by or relates"]
    seen = []
    problems = []
    for cards in lists.values():
        for card in cards:
            if card == values["key"]:
                problems.append("a card cannot link to itself")
            elif card in seen:
                problems.append(f"{card} appears in more than one list")
            seen.append(card)
    return list(dict.fromkeys(problems))


def calls(plan: dict) -> list[dict]:
    return [
        {"method": call["method"], "path": call["path"], "body": call["body"]}
        for step in plan["steps"]
        for call in step["native"]
    ]


def _material(site: str, requests: list[dict], before: list, summary: list[str]) -> dict:
    """What the approval code covers: what is sent, the state of the cards the preview showed as
    "before" and the text the person reads when approving, so the text cannot differ from what
    is sent."""
    return {
        "site": site.rstrip("/"),
        "requests": [
            {"method": call["method"], "path": call["path"], "body": call["body"]}
            for call in requests
        ],
        "before": before,
        "summary": summary,
    }


def digest_material(plan: dict) -> dict:
    before = [step["before"] for step in plan["steps"]]
    return _material(plan["target"], calls(plan), before, plan["summary"])


def plan_code(plan: dict) -> str:
    return approval.digest(digest_material(plan))


def record_code(record: dict) -> str:
    """The code of a pending record's own material; it is the record's `code` while the record
    is as `pending_record` wrote it."""
    return approval.digest(
        _material(record["site"], record["requests"], record["before"], record["summary"])
    )


def pending_record(plan: dict, *, created_at: str, sid: int) -> dict:
    material = digest_material(plan)
    return {
        "code": plan_code(plan),
        "created_at": created_at,
        "site": material["site"],
        "today": plan["today"],
        "sid": sid,
        "drafts": [step["draft"] for step in plan["steps"]],
        "requests": material["requests"],
        "before": material["before"],
        "summary": material["summary"],
    }


def apply_steps(writer, plan: dict, send: Callable[[dict], object]) -> Iterator[dict]:
    for step in plan["steps"]:
        sent: list[dict] = []
        first = None
        try:
            for call in step["native"]:
                reply = send(call)
                if not sent:
                    first = reply
                sent.append(call)
        except TrackerError as error:
            uncertain = bool(getattr(error, "uncertain", False))
            yield _result(step, "uncertain" if uncertain else "failed", sent, str(error))
            return
        except Exception as error:
            yield _result(step, "uncertain", sent, f"{type(error).__name__}: {error}")
            return
        try:
            created = writer.created_key(first) if step["op"] == "create" else None
            key = created or step["card"]
            url = writer.card_url(key) if key else None
        except Exception as error:
            yield _result(step, "uncertain", sent, f"{type(error).__name__}: {error}")
            return
        yield _result(step, "applied", sent, None, created=created, url=url)


def _result(
    step: dict,
    status: str,
    sent: list[dict],
    error: str | None,
    *,
    created: str | None = None,
    url: str | None = None,
) -> dict:
    return {
        "draft": step["draft"],
        "status": status,
        "sent": sent,
        "created": created,
        "url": url,
        "error": error,
    }
