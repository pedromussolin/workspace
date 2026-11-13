"""Draft files of `ws card`: TOML front matter between `+++` lines, then a Markdown body."""

import hashlib
import re
import tomllib
from dataclasses import dataclass
from datetime import date

from ws.tracker.vocab import ALL_TYPES, CARD_TYPES, LINK_KINDS, UPPER_TYPES

OPS = ("create", "edit", "move", "comment", "worklog", "link")

REQUIRED = {
    "create": {"type", "priority"},
    "edit": {"key"},
    "move": {"key", "to"},
    "comment": {"key"},
    "worklog": {"key", "time"},
    "link": {"key"},
}
OPTIONAL = {
    "create": {"epic", "parent", "assignee", "reporter", "sprint", "due"},
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
    },
    "move": set(),
    "comment": set(),
    "worklog": {"day"},
    "link": set(LINK_KINDS),
}
DATE_KEYS = {"start", "due", "day"}
LIST_KEYS = set(LINK_KINDS)

_DATE_TEXT = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FENCE = "+++"


class DraftError(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Draft:
    op: str
    values: dict
    title: str | None
    body: str
    sha256: str


def parse_draft(raw: bytes) -> Draft:
    digest = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise DraftError(["draft is not valid UTF-8"]) from None
    lines = text.removeprefix("﻿").splitlines()
    if not lines or lines[0].strip() != _FENCE:
        raise DraftError([f"draft must start with a {_FENCE} front matter line"])
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == _FENCE)
    except StopIteration:
        raise DraftError([f"front matter is not closed by a {_FENCE} line"]) from None
    try:
        front = tomllib.loads("\n".join(lines[1:end]))
    except tomllib.TOMLDecodeError as error:
        raise DraftError([f"front matter is not valid TOML: {error}"]) from None
    body_lines = lines[end + 1 :]
    op = front.get("op")
    if op not in OPS:
        raise DraftError([f"op must be one of {', '.join(OPS)}"])
    values = _values(op, front)
    if op == "link" and any(line.strip() for line in body_lines):
        raise DraftError(["a link draft has no body"])
    title = None
    if op == "create":
        title, body_lines = _split_title(body_lines)
    return Draft(op, values, title, "\n".join(body_lines), digest)


def _values(op: str, front: dict) -> dict:
    problems = []
    allowed = REQUIRED[op] | OPTIONAL[op] | {"op"}
    for name in sorted(set(front) - allowed):
        problems.append(f"unknown key {name!r} for op {op}")
    for name in sorted(REQUIRED[op] - set(front)):
        problems.append(f"missing key {name!r} for op {op}")
    values = {}
    for name in sorted(set(front) & (allowed - {"op"})):
        if name in LIST_KEYS:
            parsed = _keys(front[name])
        elif name in DATE_KEYS:
            parsed = _date(front[name])
        else:
            parsed = _string(front[name])
        if parsed is None:
            kind = "a date (YYYY-MM-DD)" if name in DATE_KEYS else "a non-empty string"
            if name in LIST_KEYS:
                kind = "a list of card keys"
            problems.append(f"{name} must be {kind}")
        elif name in LIST_KEYS and len(set(parsed)) != len(parsed):
            twice = next(item for item in parsed if parsed.count(item) > 1)
            problems.append(f"{name} lists {twice} twice")
        else:
            values[name] = parsed
    if not problems:
        problems = _cross_rules(op, values)
    if problems:
        raise DraftError(problems)
    return values


def _cross_rules(op: str, values: dict) -> list[str]:
    problems = []
    kind = values.get("type")
    if kind is not None and kind not in ALL_TYPES:
        problems.append(f"type must be one of {', '.join(ALL_TYPES)}")
    elif op == "create":
        problems += _create_rules(kind, values)
    elif op == "edit":
        problems += _edit_rules(kind, values)
    if "sprint" in values and values["sprint"] != "active":
        problems.append('sprint must be "active"')
    if op == "link":
        problems += _link_rules(values)
    return problems


def _create_rules(kind: str, values: dict) -> list[str]:
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


def _keys(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = [_string(item) for item in value]
    return None if None in items else items


def _string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _date(value: object) -> date | None:
    if type(value) is date:
        return value
    if isinstance(value, str) and _DATE_TEXT.match(value.strip()):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def _split_title(lines: list[str]) -> tuple[str, list[str]]:
    """The first non-blank line is `# title`. The title line becomes blank, so the line numbers
    the converter reports still count from the first line after the front matter."""
    for index, line in enumerate(lines):
        if line.strip():
            if not line.startswith("# ") or not line[2:].strip():
                raise DraftError(["the body must start with a '# title' line (create)"])
            return line[2:].strip(), [""] * (index + 1) + lines[index + 1 :]
    raise DraftError(["the body must start with a '# title' line (create)"])
